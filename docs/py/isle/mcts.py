"""サイコロと隠れ札を引いて読む探索（決定化した MCTS、葉は評価関数）。

手番の中の手（MAIN の場面）を選ぶときだけ探索する。やり方:

1. 貪欲AIの1手先の評価で手を並べ、上位 k 手（と「手番を終える」）を候補にする。
2. 1回の読みごとに、見えない所を引き直す（決定化）:
   - 発展カードの山の順番と、相手が持っている発展カードの中身（見えない札をまとめて配り直す）
   - この先のサイコロ・盗むカード・山から引くカードは、新しい乱数で引く
3. 候補の手を打ち、全員を貪欲AIで動かして、自分の次の手番が来るまで（1巡）進める。
4. 葉の値は、4人の評価関数の値を softmax にした「自分の勝ちやすさ」（勝ったら1、負けたら0）。
5. 候補の選び方は UCB1（Kocsis & Szepesvári 2006）。木は根だけ持つ（読みごとに隠れた所が違うので、
   深い所の手は同じ節点にまとめにくい。Cowling, Powley, Whitehouse 2012 の ISMCTS の根の部分）。

勝てる手番は先に `find_win` で厳密に探す（WinCheckAgent と同じ）。
"""

from __future__ import annotations

import math
import random

from .agents import MAX_ACTIONS_PER_TURN, GreedyAgent, WinCheckAgent
from .features import DEFAULT_WEIGHTS, evaluate
from .game import MAIN, PRE_ROLL, Game
from .solver import find_win

ROLLOUT_LIMIT = 400  # 1回の読みの手の数の上限（安全弁）


def determinize(g: Game, me: int, rng: random.Random) -> Game:
    """me から見えない所を引き直した写しを作る（もとの g は変えない）。

    見えないもの: 山の順番・相手の発展カードの中身（枚数は見える）・この先の乱数。
    手札の資源は数えればほぼ分かるので、そのまま使う（盗まれた札は相手の手札の中身ごと見えている扱い）。
    """
    c = g.clone(keep_rng=False)
    c.rng = random.Random(rng.getrandbits(64))
    pool = list(c.dev_deck)
    counts = []
    for q, pl in enumerate(c.players):
        if q == me:
            continue
        # 買ったばかりの札（dev_new）も中身は見えないので、まとめて配り直す
        n_old = sum(pl.dev) - sum(pl.dev_new)
        n_new = sum(pl.dev_new)
        for card in range(5):
            pool += [card] * pl.dev[card]
        counts.append((q, n_old, n_new))
    rng.shuffle(pool)
    for q, n_old, n_new in counts:
        pl = c.players[q]
        pl.dev = [0] * 5
        pl.dev_new = [0] * 5
        for _ in range(n_old):
            pl.dev[pool.pop()] += 1
        for _ in range(n_new):
            card = pool.pop()
            pl.dev[card] += 1
            pl.dev_new[card] += 1
    c.dev_deck = pool
    # 相手が引き直しで10点に届いてしまうのは見えない札の偶然。そのまま続ける（次の確認で勝ちになる）
    c._check_win()
    return c


def leaf_value(g: Game, me: int, temp: float, weights=DEFAULT_WEIGHTS) -> float:
    if g.winner is not None:
        return 1.0 if g.winner == me else 0.0
    vals = [evaluate(g, q, weights) for q in range(g.n)]
    m = max(vals)
    ex = [math.exp((v - m) / temp) for v in vals]
    return ex[me] / sum(ex)


class MCTSAgent(WinCheckAgent):
    name = "mcts"

    def __init__(
        self,
        weights=DEFAULT_WEIGHTS,
        seed: int | None = None,
        sims: int = 48,
        top_k: int = 5,
        c_ucb: float = 0.5,
        temp: float = 1.0,
    ):
        super().__init__(weights, seed)
        self.sims = sims
        self.top_k = top_k
        self.c_ucb = c_ucb
        self.temp = temp
        self.search_rng = random.Random(None if seed is None else seed * 7919 + 1)
        self.searches = 0

    def act(self, g: Game) -> tuple:
        if g.phase != MAIN or g.to_act != g.current:
            return super().act(g)
        turn = (g.turns, g.current)
        acts = g.legal_actions()
        # 勝ち筋（find_win）は親クラスと同じに扱う
        if self._plan and self._plan_turn == turn:
            a = self._plan[0]
            if a in acts:
                self._plan.pop(0)
                return a
            self._plan = []
            self._checked_turn = None
        if self._checked_turn != turn:
            self._checked_turn = turn
            line = find_win(g)
            if line:
                self._plan, self._plan_turn = list(line[1:]), turn
                return line[0]
        if len(acts) == 1:
            return acts[0]
        if turn != self._turn_key:
            self._turn_key, self._turn_actions = turn, 0
        self._turn_actions += 1
        if self._turn_actions > MAX_ACTIONS_PER_TURN:
            return ("end",)
        return self.search(g, acts)

    def candidates(self, g: Game, acts: list[tuple]) -> list[tuple]:
        p = g.to_act
        scored = sorted(
            acts, key=lambda a: self._action_value(g, p, a) + (1e-6 if a == ("end",) else 0.0)
        )
        top = scored[::-1][: self.top_k]
        if ("end",) not in top:
            top.append(("end",))
        return top

    def search(self, g: Game, acts: list[tuple]) -> tuple:
        me = g.to_act
        cands = self.candidates(g, acts)
        if len(cands) == 1:
            return cands[0]
        self.searches += 1
        n = [0] * len(cands)
        w = [0.0] * len(cands)
        rollout = _RolloutPolicy(self.w, self.search_rng.getrandbits(32))
        # 同じ乱数の読み（common random numbers）: 候補 i の k 回目の読みは、どの候補でも
        # k 番目の決定化・出目を使う。候補どうしの差が運のぶれに埋もれにくくなる
        seeds: list[int] = []
        for t in range(self.sims):
            if t < len(cands):
                i = t
            else:
                lt = math.log(t)
                i = max(
                    range(len(cands)),
                    key=lambda j: w[j] / n[j] + self.c_ucb * math.sqrt(lt / n[j]),
                )
            while len(seeds) <= n[i]:
                seeds.append(self.search_rng.getrandbits(64))
            c = determinize(g, me, random.Random(seeds[n[i]]))
            if c.winner is None:
                c.apply(cands[i])
                _play_until_my_next_turn(c, me, rollout)
            w[i] += leaf_value(c, me, self.temp, self.w)
            n[i] += 1
        best = max(range(len(cands)), key=lambda j: (n[j], w[j] / n[j]))
        return cands[best]


class _RolloutPolicy(GreedyAgent):
    """読みの中で全員を動かす貪欲AI（勝ち筋の探索なし、速さのため）。"""

    name = "rollout"


def _play_until_my_next_turn(c: Game, me: int, policy: GreedyAgent) -> None:
    """自分の今の手番の残りと相手3人の手番を進め、自分の次のサイコロの前で止める。"""
    start_turns = c.turns
    for _ in range(ROLLOUT_LIMIT):
        if c.is_over():
            return
        if c.current == me and c.phase == PRE_ROLL and c.turns > start_turns:
            return
        c.apply(policy.act(c))
