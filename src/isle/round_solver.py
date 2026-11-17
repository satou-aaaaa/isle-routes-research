"""終盤1巡の読み切り（GTO の物差し2）。

ある人（根）の手番のサイコロのあとから、相手3人の手番と、根の次の手番までを、
サイコロの確率どおりに全部読む。値は「この1巡のうちに根が勝つ確率」。

- 根の手番: 打てる手を全部読む
  （発展カードを買う手は山札の中身の割合で、盗むカードは相手の手札の割合で平均）。
- 相手の手番: 出目ごとに分ける。その手番で勝てる筋があれば勝つ（solver.find_win）。
  勝てないときは建てずに手番を終える（近似。この1巡では建てても相手自身の勝ちにはつながらない）。
  7のときの盗賊の置き場・盗む相手の決め方で、相手の考え方を2通りにする（Sturtevant & Korf 2000）。
    - max^n: 相手は自分がこの手番で勝つ確率を最大にする。同じなら貪欲AIと同じ所へ置く。
    - paranoid: 相手は全員、根が勝つ確率を一番下げる所へ置く。
- 根の次の手番: 出目ごとに、その手番で勝てる筋があれば勝ち（7なら盗む相手を選んでから）。
- 7で手札を捨てるのは全員「一番多い資源から」の決まった手順（近似）。
- 相手の手番の最初の騎士・発展カードを買う手は読まない（近似）。
"""

from __future__ import annotations

import time
from collections.abc import Callable

from .agents import GreedyAgent
from .board import TOPO, dice_ways
from .game import DISCARD, FREE_ROAD, MAIN, MONOPOLY, OVER, PRE_ROLL, ROBBER, STEAL, Game
from .solver import could_win, find_win

MAXN, PARANOID = "maxn", "paranoid"
DICE = [(d, dice_ways(d) / 36) for d in range(2, 13)]


class TooBig(Exception):
    """読む局面が上限を超えた（測定から外す）。"""


def full_key(g: Game) -> tuple:
    return (
        g.current,
        g.phase,
        g.robber,
        g.dev_played,
        g.free_roads,
        g.longest_holder,
        g.army_holder,
        tuple(g.building),
        tuple(g.is_city),
        tuple(g.road),
        tuple(g.bank),
        tuple(
            tuple(pl.hand) + tuple(pl.dev) + tuple(pl.dev_new) + (pl.knights,) for pl in g.players
        ),
        tuple(sorted(g.dev_deck)),
        tuple(g.discard_queue),
    )


def do_discards(g: Game) -> None:
    """7で8枚以上の人が半分捨てる。一番多い資源から1枚ずつ（同じなら番号の小さい資源）。"""
    while g.phase == DISCARD:
        q = g.discard_queue[0][0]
        hand = g.players[q].hand
        g.apply(("discard", max(range(5), key=lambda r: (hand[r], -r))))


def steal_outcomes(g: Game, q: int) -> list[tuple[float, Game]]:
    """STEAL の場面で q から盗む: 盗むカードの種類ごとの (確率, 局面)。"""
    hand = g.players[q].hand
    total = sum(hand)
    out = []
    for r in range(5):
        if hand[r]:
            c = g.clone(keep_rng=False)
            c.players[q].hand[r] -= 1
            c.players[c.current].hand[r] += 1
            c._after_robber()
            out.append((hand[r] / total, c))
    return out


def dev_outcomes(g: Game) -> list[tuple[float, Game]]:
    """発展カードを買う手: 山札の中身の割合で、引くカードの種類ごとの (確率, 局面)。"""
    deck = g.dev_deck
    out = []
    for card in sorted(set(deck)):
        c = g.clone(keep_rng=False)
        i = c.dev_deck.index(card)
        c.dev_deck.append(c.dev_deck.pop(i))
        c.apply(("buy_dev",))
        out.append((deck.count(card) / len(deck), c))
    return out


class RoundSolver:
    def __init__(
        self,
        root: int,
        mode: str = MAXN,
        max_nodes: int = 4000,
        max_ends: int = 600,
        max_seconds: float | None = None,
    ):
        if mode not in (MAXN, PARANOID):
            raise ValueError(mode)
        self.root = root
        self.mode = mode
        self.max_nodes = max_nodes
        self.max_ends = max_ends
        self.deadline = None if max_seconds is None else time.monotonic() + max_seconds
        self.nodes = 0
        self._turn_memo: dict = {}
        self._end_memo: dict = {}
        self._win_memo: dict = {}
        self._greedy = GreedyAgent(seed=0)

    # ---- 根の手番 ----
    def value(self, g: Game) -> float:
        """根の手番（サイコロのあと）から読んだ、この1巡で根が勝つ確率（根は最善を打つ）。"""
        return self._turn(g, None)

    def agent_value(self, g: Game, choose: Callable[[Game, int], tuple]) -> float:
        """根だけ choose(局面, この手番で打った手の数) で打ったときの値。"""
        return self._turn(g, choose, 0)

    def _turn(self, s: Game, choose, depth: int = 0) -> float:
        if s.phase == OVER:
            return 1.0 if s.winner == self.root else 0.0
        if s.current != self.root:
            return self._after_end(s)
        key = None
        if choose is None:
            key = full_key(s)
            if key in self._turn_memo:
                return self._turn_memo[key]
            self.nodes += 1
            if self.nodes > self.max_nodes:
                raise TooBig("root nodes")
        if s.phase == STEAL and choose is None:
            v = max(self._steal_value(s, q, choose, depth) for q in s._steal_targets())
        elif choose is not None:
            a = choose(s, depth)
            v = self._action_value(s, a, choose, depth)
        else:
            v = max(self._action_value(s, a, None, depth) for a in s.legal_actions())
        if key is not None:
            self._turn_memo[key] = v
        return v

    def _steal_value(self, s: Game, q: int, choose, depth: int) -> float:
        return sum(pr * self._turn(c, choose, depth + 1) for pr, c in steal_outcomes(s, q))

    def _action_value(self, s: Game, a: tuple, choose, depth: int) -> float:
        if a[0] == "steal":
            return self._steal_value(s, a[1], choose, depth)
        if a[0] == "buy_dev":
            return sum(pr * self._turn(c, choose, depth + 1) for pr, c in dev_outcomes(s))
        c = s.clone(keep_rng=False)
        c.apply(a)
        return self._turn(c, choose, depth + 1)

    # ---- 根が手番を終えたあと ----
    def _after_end(self, s: Game) -> float:
        key = full_key(s)
        if key in self._end_memo:
            return self._end_memo[key]
        if len(self._end_memo) >= self.max_ends:
            raise TooBig("end states")
        self._check_time()
        if not self._root_may_win_next(s):
            self._end_memo[key] = 0.0  # 次の手番にどう出目が出ても届かない
            return 0.0
        self._w_memo: dict = {}
        v = self._w(s, 1)
        self._end_memo[key] = v
        return v

    def _check_time(self) -> None:
        if self.deadline is not None and time.monotonic() > self.deadline:
            raise TooBig("time")

    def _root_may_win_next(self, s: Game) -> bool:
        """相手3人と自分の4回のサイコロで一番多くもらえたとしても、次の手番に届かないなら False。"""
        root = self.root
        pl = s.players[root]
        if pl.dev[MONOPOLY] > 0:
            return True  # 相手の手札しだいで増えるので見積もらない
        per_roll = [0] * 13
        for v, b in enumerate(s.building):
            if b == root:
                k = 2 if s.is_city[v] else 1
                for _h, _r, num in s.vertex_yield[v]:
                    per_roll[num] += k
        return could_win(s, root, extra_cards=4 * max(per_roll) + 1)

    def _w(self, s: Game, k: int) -> float:
        """手番 k 人目（1〜3 は相手、4 は根の次の手番）の、サイコロを振る前の局面からの値。"""
        if s.phase == OVER:
            return 1.0 if s.winner == self.root else 0.0
        key = (k, s.robber, tuple(tuple(pl.hand) for pl in s.players))
        if key in self._w_memo:
            return self._w_memo[key]
        self._check_time()  # 1つの終わり方の先も大きいので、ここでも時間を見る
        assert s.phase == PRE_ROLL
        v = 0.0
        for d, pr in DICE:
            c = s.clone(keep_rng=False)
            c._roll(d)
            v += pr * (self._root_next(c) if k == 4 else self._opp_rolled(c, k))
        self._w_memo[key] = v
        return v

    def _can_win(self, s: Game) -> bool:
        p = s.current
        pl = s.players[p]
        # 勝ち筋に効くのは自分の手札と、独占で集められる相手の手札の合計だけ
        others = None
        if pl.dev[MONOPOLY] - pl.dev_new[MONOPOLY] > 0:
            others = tuple(
                sum(o.hand[r] for q, o in enumerate(s.players) if q != p) for r in range(5)
            )
        key = (
            p,
            s.robber,
            tuple(pl.hand),
            others,
            tuple(pl.dev),
            pl.knights,
            s.longest_holder,
            s.army_holder,
            tuple(s.building),
            tuple(s.is_city),
            tuple(s.road),
            # 銀行は、この手番で受け取れる枚数（2:1 交換で手札の半分＋豊作2枚）を超える分は効かない
            tuple(min(b, pl.cards() // 2 + 2) for b in s.bank),
        )
        if key not in self._win_memo:
            self._win_memo[key] = find_win(s) is not None
        return self._win_memo[key]

    def _win_prob(self, opts: list[tuple[float, Game]]) -> float:
        return sum(pr * self._can_win(c) for pr, c in opts)

    @staticmethod
    def _hex_targets(s: Game) -> dict[int, list[int]]:
        """盗賊を置ける六角形ごとの、盗める相手（いなければ空）。"""
        out = {}
        me = s.current
        for h in range(len(s.layout.terrain)):
            if h == s.robber:
                continue
            qs = set()
            for v in TOPO.hex_vertices[h]:
                q = s.building[v]
                if q not in (-1, me) and s.players[q].cards() > 0:
                    qs.add(q)
            out[h] = sorted(qs)
        return out

    @staticmethod
    def _place(s: Game, h: int, q: int | None) -> list[tuple[float, Game]]:
        """盗賊を h に置き、q から盗む（q が None なら盗まない）: (確率, MAIN の局面)。"""
        c = s.clone(keep_rng=False)
        c.robber = h
        if q is None:
            c._after_robber()
            return [(1.0, c)]
        c.phase = STEAL
        return steal_outcomes(c, q)

    def _by_victim(self, s: Game) -> dict:
        """盗む相手（None は盗まない）ごとに、貪欲AIの目安で一番よい置き場。"""
        targets = self._hex_targets(s)
        groups: dict = {}
        for h, qs in targets.items():
            for q in qs or [None]:
                groups.setdefault(q, []).append(h)
        out = {}
        for q, hexes in groups.items():
            acts = [("robber", h) for h in hexes]
            out[q] = acts[0][1] if len(acts) == 1 else self._greedy._robber(s, s.current, acts)[1]
        return out

    def _root_next(self, s: Game) -> float:
        do_discards(s)
        if s.phase == MAIN:
            return float(self._can_win(s))
        # 7: 盗む相手ごとに1つずつ（置き場はこの手番の勝ちにほぼ関係しない）
        best = 0.0
        for q, h in self._by_victim(s).items():
            best = max(best, self._win_prob(self._place(s, h, q)))
            if best == 1.0:
                break
        return best

    def _opp_rolled(self, s: Game, k: int) -> float:
        do_discards(s)
        if s.phase == MAIN:
            return self._opp_main(s, k)
        h0, q0 = self._maxn_choice(s)
        if self.mode == PARANOID:
            mine = [v for v in range(len(s.building)) if s.building[v] == self.root]
            near = {h for v in mine for h in TOPO.vertex_hexes[v]}
            cand = {(h0, q0)}
            for h, qs in self._hex_targets(s).items():
                if h in near:
                    cand.update((h, q) for q in qs or [None])
            return min(
                sum(pr * self._opp_main(c, k) for pr, c in self._place(s, h, q)) for h, q in cand
            )
        return sum(pr * self._opp_main(c, k) for pr, c in self._place(s, h0, q0))

    def _maxn_choice(self, s: Game) -> tuple[int, int | None]:
        """相手が自分の勝つ確率を最大にする (置き場, 盗む相手)。同じなら貪欲AIの選び方。"""
        g_hex = self._greedy._robber(s, s.current, s.legal_actions())[1]
        g_targets = self._hex_targets(s)[g_hex]
        g_q = (
            max(g_targets, key=lambda q: (s.vp(q, hidden=False), s.players[q].cards()))
            if g_targets
            else None
        )
        by_q = self._by_victim(s)
        probs = {q: self._win_prob(self._place(s, h, q)) for q, h in by_q.items()}
        top = max(probs.values())
        if probs.get(g_q, -1.0) == top:
            return g_hex, g_q
        q = next(q for q in by_q if probs[q] == top)
        return by_q[q], q

    def _opp_main(self, s: Game, k: int) -> float:
        if s.phase == OVER:
            return 1.0 if s.winner == self.root else 0.0
        if self._can_win(s):
            return 0.0
        c = s.clone(keep_rng=False)
        c.apply(("end",))
        return self._w(c, k + 1)


def agent_chooser(agent) -> Callable[[Game, int], tuple]:
    """エージェントを、手番の中で打った手の数を渡して1手ずつ選ぶ関数にする（読み切りの中で使う）。

    greedy_win は手番の最初にだけ勝ち筋を探す（実際の WinCheckAgent と同じ）。
    """
    from .agents import WinCheckAgent

    plans: dict = {}

    def choose(g: Game, depth: int) -> tuple:
        if isinstance(agent, WinCheckAgent):
            if depth == 0:
                line = find_win(g) if g.phase == MAIN else None
                plans.clear()
                if line:
                    plans[0] = list(line)
            plan = plans.get(0)
            if plan:
                a = plan[0]
                if a in g.legal_actions():
                    plans[0] = plan[1:]
                    return a
                plans.clear()
        agent._turn_key = (g.turns, g.current)
        agent._turn_actions = depth
        return GreedyAgent.act(agent, g)

    return choose


ROOT_PHASES = (MAIN, ROBBER, STEAL, FREE_ROAD)
