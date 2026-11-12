"""ルールエンジン（基本ルール・4人・人どうしの交換なし）。

手は tuple で表す。legal_actions() で今打てる手の一覧、apply() で1手進める。
サイコロ・盗むカード・発展カードの山は state.rng で決まる（seed で再現できる）。

手の一覧:
    ("settle", v) / ("road", e)          初期配置
    ("roll",)                            サイコロを振る
    ("discard", r)                       7のとき手札を1枚捨てる（捨て終わるまで繰り返す）
    ("robber", h) / ("steal", p)         盗賊を動かす / 盗む相手を選ぶ
    ("build_road", e) / ("build_settlement", v) / ("build_city", v)
    ("buy_dev",)
    ("knight",) / ("road_building",) / ("plenty", r1, r2) / ("monopoly", r)
    ("free_road", e)                     道づくりカードの道
    ("trade", give, get)                 銀行・港との交換
    ("end",)                             手番を終える
"""

from __future__ import annotations

import copy
import random
from dataclasses import dataclass, field

from .board import (
    DESERT,
    GENERIC,
    N_EDGE,
    N_HEX,
    N_VERTEX,
    RESOURCES,
    TOPO,
    Layout,
    random_layout,
)

KNIGHT, VP_CARD, ROAD_BUILDING, PLENTY, MONOPOLY = range(5)
DEV_DECK = (KNIGHT,) * 14 + (VP_CARD,) * 5 + (ROAD_BUILDING, PLENTY, MONOPOLY) * 2

COST = {
    "road": (1, 1, 0, 0, 0),  # 木材・れんが
    "settlement": (1, 1, 1, 1, 0),  # 木材・れんが・羊毛・小麦
    "city": (0, 0, 0, 2, 3),  # 小麦2・鉱石3
    "dev": (0, 0, 1, 1, 1),  # 羊毛・小麦・鉱石
}
MAX_ROADS, MAX_SETTLEMENTS, MAX_CITIES = 15, 5, 4
BANK_EACH = 19
WIN_VP = 10
LONGEST_MIN = 5
ARMY_MIN = 3
MAX_TURNS = 1000  # 終わらない対局を止める安全弁

# 場面
SETUP_SETTLE, SETUP_ROAD, PRE_ROLL, DISCARD, ROBBER, STEAL, MAIN, FREE_ROAD, OVER = range(9)


@dataclass
class Player:
    hand: list[int] = field(default_factory=lambda: [0] * 5)
    dev: list[int] = field(default_factory=lambda: [0] * 5)  # 持っている発展カード
    dev_new: list[int] = field(default_factory=lambda: [0] * 5)  # この手番に買った分
    knights: int = 0  # 使った騎士
    roads: int = 0
    settlements: int = 0
    cities: int = 0

    def cards(self) -> int:
        return sum(self.hand)


class Game:
    def __init__(self, n_players: int = 4, seed: int | None = None, layout: Layout | None = None):
        self.rng = random.Random(seed)
        self.n = n_players
        self.layout = layout or random_layout(self.rng)
        self.vertex_port = self.layout.vertex_port()
        self.players = [Player() for _ in range(n_players)]
        self.bank = [BANK_EACH] * 5
        deck = list(DEV_DECK)
        self.rng.shuffle(deck)
        self.dev_deck = deck
        self.building = [-1] * N_VERTEX  # 頂点の持ち主
        self.is_city = [False] * N_VERTEX
        self.road = [-1] * N_EDGE  # 辺の持ち主
        self.robber = self.layout.desert
        self.longest_holder: int | None = None
        self.longest_len = [0] * n_players
        self.army_holder: int | None = None
        # 初期配置の順: 0,1,2,3,3,2,1,0
        self.setup_order = list(range(n_players)) + list(reversed(range(n_players)))
        self.setup_step = 0
        self.current = 0
        self.phase = SETUP_SETTLE
        self.last_settlement = -1
        self.rolled = False
        self.dev_played = False
        self.discard_queue: list[tuple[int, int]] = []  # (人, 残り枚数)
        self.free_roads = 0
        self.turns = 0
        self.last_roll = 0
        self.winner: int | None = None
        # 頂点ごとの産出（六角形, 資源, 数字）を先に計算
        self.vertex_yield = [
            [
                (h, self.layout.terrain[h], self.layout.number[h])
                for h in TOPO.vertex_hexes[v]
                if self.layout.terrain[h] != DESERT
            ]
            for v in range(N_VERTEX)
        ]

    # ---- 便利関数 ----
    def clone(self) -> Game:
        return copy.deepcopy(self)

    @property
    def to_act(self) -> int:
        if self.phase == DISCARD:
            return self.discard_queue[0][0]
        return self.current

    def vp(self, p: int, hidden: bool = True) -> int:
        pl = self.players[p]
        v = pl.settlements + 2 * pl.cities
        if self.longest_holder == p:
            v += 2
        if self.army_holder == p:
            v += 2
        if hidden:
            v += pl.dev[VP_CARD]
        return v

    def is_over(self) -> bool:
        return self.phase == OVER

    def _can_pay(self, p: int, cost) -> bool:
        return all(h >= c for h, c in zip(self.players[p].hand, cost, strict=True))

    def _pay(self, p: int, cost) -> None:
        hand = self.players[p].hand
        for r, c in enumerate(cost):
            hand[r] -= c
            self.bank[r] += c

    def _take_from_bank(self, p: int, r: int, k: int = 1) -> None:
        k = min(k, self.bank[r])
        self.bank[r] -= k
        self.players[p].hand[r] += k

    def _vertex_free(self, v: int) -> bool:
        """空いていて、となりの頂点にも建物がない（距離のきまり）。"""
        if self.building[v] != -1:
            return False
        return all(self.building[u] == -1 for u in TOPO.vertex_neighbors[v])

    def _touches_own_road(self, p: int, v: int) -> bool:
        return any(self.road[e] == p for e in TOPO.vertex_edges[v])

    def _road_ok(self, p: int, e: int) -> bool:
        if self.road[e] != -1:
            return False
        for v in TOPO.edges[e]:
            owner = self.building[v]
            if owner == p:
                return True
            if owner != -1:
                continue  # 他人の建物の先にはつながらない
            if any(self.road[f] == p for f in TOPO.vertex_edges[v] if f != e):
                return True
        return False

    def _trade_ratio(self, p: int, r: int) -> int:
        ratio = 4
        for v, kind in self.vertex_port.items():
            if self.building[v] == p:
                if kind == r:
                    return 2
                if kind == GENERIC:
                    ratio = 3
        return ratio

    def _playable(self, p: int, card: int) -> bool:
        pl = self.players[p]
        return not self.dev_played and pl.dev[card] - pl.dev_new[card] > 0

    # ---- 打てる手 ----
    def legal_actions(self) -> list[tuple]:
        ph, p = self.phase, self.current
        pl = self.players[p]
        if ph == OVER:
            return []
        if ph == SETUP_SETTLE:
            return [("settle", v) for v in range(N_VERTEX) if self._vertex_free(v)]
        if ph == SETUP_ROAD:
            v = self.last_settlement
            return [("road", e) for e in TOPO.vertex_edges[v] if self.road[e] == -1]
        if ph == PRE_ROLL:
            acts = [("roll",)]
            if self._playable(p, KNIGHT):
                acts.append(("knight",))
            return acts
        if ph == DISCARD:
            q = self.discard_queue[0][0]
            return [("discard", r) for r in RESOURCES if self.players[q].hand[r] > 0]
        if ph == ROBBER:
            return [("robber", h) for h in range(N_HEX) if h != self.robber]
        if ph == STEAL:
            return [("steal", q) for q in self._steal_targets()]
        if ph == FREE_ROAD:
            return [("free_road", e) for e in range(N_EDGE) if self._road_ok(p, e)]
        # MAIN
        acts: list[tuple] = [("end",)]
        if pl.roads < MAX_ROADS and self._can_pay(p, COST["road"]):
            acts += [("build_road", e) for e in range(N_EDGE) if self._road_ok(p, e)]
        if pl.settlements < MAX_SETTLEMENTS and self._can_pay(p, COST["settlement"]):
            acts += [
                ("build_settlement", v)
                for v in range(N_VERTEX)
                if self._vertex_free(v) and self._touches_own_road(p, v)
            ]
        if pl.cities < MAX_CITIES and self._can_pay(p, COST["city"]):
            acts += [
                ("build_city", v)
                for v in range(N_VERTEX)
                if self.building[v] == p and not self.is_city[v]
            ]
        if self.dev_deck and self._can_pay(p, COST["dev"]):
            acts.append(("buy_dev",))
        if self._playable(p, KNIGHT):
            acts.append(("knight",))
        if self._playable(p, ROAD_BUILDING) and pl.roads < MAX_ROADS:
            acts.append(("road_building",))
        if self._playable(p, PLENTY):
            acts += [
                ("plenty", a, b)
                for a in RESOURCES
                for b in RESOURCES
                if a <= b and self.bank[a] > 0 and self.bank[b] > (1 if a == b else 0)
            ]
        if self._playable(p, MONOPOLY):
            acts += [("monopoly", r) for r in RESOURCES]
        for give in RESOURCES:
            ratio = self._trade_ratio(p, give)
            if pl.hand[give] >= ratio:
                acts += [
                    ("trade", give, get) for get in RESOURCES if get != give and self.bank[get] > 0
                ]
        return acts

    def _steal_targets(self) -> list[int]:
        out = set()
        for v in TOPO.hex_vertices[self.robber]:
            q = self.building[v]
            if q not in (-1, self.current) and self.players[q].cards() > 0:
                out.add(q)
        return sorted(out)

    # ---- 1手進める ----
    def apply(self, a: tuple) -> None:
        kind = a[0]
        p = self.current
        pl = self.players[p]
        if kind == "settle":
            v = a[1]
            self.building[v] = p
            pl.settlements += 1
            self.last_settlement = v
            if self.setup_step >= self.n:  # 2つ目の開拓地: まわりの資源をもらう
                for _h, r, _n in self.vertex_yield[v]:
                    self._take_from_bank(p, r)
            self.phase = SETUP_ROAD
        elif kind == "road":
            self.road[a[1]] = p
            pl.roads += 1
            self.setup_step += 1
            if self.setup_step >= len(self.setup_order):
                self.current = 0
                self._start_turn()
            else:
                self.current = self.setup_order[self.setup_step]
                self.phase = SETUP_SETTLE
        elif kind == "roll":
            self._roll()
        elif kind == "discard":
            q, left = self.discard_queue[0]
            r = a[1]
            self.players[q].hand[r] -= 1
            self.bank[r] += 1
            left -= 1
            if left:
                self.discard_queue[0] = (q, left)
            else:
                self.discard_queue.pop(0)
            if not self.discard_queue:
                self.phase = ROBBER
        elif kind == "robber":
            self.robber = a[1]
            if self._steal_targets():
                self.phase = STEAL
            else:
                self._after_robber()
        elif kind == "steal":
            victim = self.players[a[1]]
            pool = [r for r in RESOURCES for _ in range(victim.hand[r])]
            r = self.rng.choice(pool)
            victim.hand[r] -= 1
            pl.hand[r] += 1
            self._after_robber()
        elif kind == "build_road":
            self._pay(p, COST["road"])
            self.road[a[1]] = p
            pl.roads += 1
            self._update_longest()
        elif kind == "free_road":
            self.road[a[1]] = p
            pl.roads += 1
            self.free_roads -= 1
            self._update_longest()
            if self.free_roads == 0 or not self.legal_actions():
                self.free_roads = 0
                self.phase = MAIN
        elif kind == "build_settlement":
            self._pay(p, COST["settlement"])
            self.building[a[1]] = p
            pl.settlements += 1
            self._update_longest()  # 他人の道を分断することがある
        elif kind == "build_city":
            self._pay(p, COST["city"])
            self.is_city[a[1]] = True
            pl.settlements -= 1
            pl.cities += 1
        elif kind == "buy_dev":
            self._pay(p, COST["dev"])
            card = self.dev_deck.pop()
            pl.dev[card] += 1
            pl.dev_new[card] += 1
        elif kind == "knight":
            self._use_dev(p, KNIGHT)
            pl.knights += 1
            self._update_army()
            self.phase = ROBBER
        elif kind == "road_building":
            self._use_dev(p, ROAD_BUILDING)
            self.free_roads = min(2, MAX_ROADS - pl.roads)
            self.phase = FREE_ROAD
            if not self.legal_actions():
                self.free_roads = 0
                self.phase = MAIN
        elif kind == "plenty":
            self._use_dev(p, PLENTY)
            self._take_from_bank(p, a[1])
            self._take_from_bank(p, a[2])
        elif kind == "monopoly":
            self._use_dev(p, MONOPOLY)
            r = a[1]
            for q, other in enumerate(self.players):
                if q != p:
                    pl.hand[r] += other.hand[r]
                    other.hand[r] = 0
        elif kind == "trade":
            give, get = a[1], a[2]
            ratio = self._trade_ratio(p, give)
            pl.hand[give] -= ratio
            self.bank[give] += ratio
            self._take_from_bank(p, get)
        elif kind == "end":
            self.current = (p + 1) % self.n
            self.turns += 1
            self._start_turn()
            return
        else:
            raise ValueError(f"unknown action {a}")
        self._check_win()

    def _use_dev(self, p: int, card: int) -> None:
        self.players[p].dev[card] -= 1
        self.dev_played = True

    def _start_turn(self) -> None:
        for pl in self.players:
            pl.dev_new = [0] * 5
        self.rolled = False
        self.dev_played = False
        self.phase = PRE_ROLL
        if self.turns >= MAX_TURNS:
            self.phase = OVER
        else:
            self._check_win()

    def _after_robber(self) -> None:
        self.phase = MAIN if self.rolled else PRE_ROLL

    def _roll(self) -> None:
        d = self.rng.randint(1, 6) + self.rng.randint(1, 6)
        self.last_roll = d
        self.rolled = True
        if d == 7:
            self.discard_queue = []
            for i in range(self.n):
                q = (self.current + i) % self.n
                c = self.players[q].cards()
                if c > 7:
                    self.discard_queue.append((q, c // 2))
            self.phase = DISCARD if self.discard_queue else ROBBER
            return
        self.produce(d)
        self.phase = MAIN

    def produce(self, d: int) -> None:
        """出目 d の産出。

        銀行が足りない資源は、もらう人が1人だけなら残りを渡し、2人以上なら誰にも渡さない。
        """
        want = [[0] * 5 for _ in range(self.n)]
        for v in range(N_VERTEX):
            q = self.building[v]
            if q == -1:
                continue
            k = 2 if self.is_city[v] else 1
            for h, r, num in self.vertex_yield[v]:
                if num == d and h != self.robber:
                    want[q][r] += k
        for r in RESOURCES:
            total = sum(w[r] for w in want)
            if total == 0:
                continue
            takers = [q for q in range(self.n) if want[q][r]]
            if total <= self.bank[r]:
                for q in takers:
                    self._take_from_bank(q, r, want[q][r])
            elif len(takers) == 1:
                self._take_from_bank(takers[0], r, self.bank[r])

    # ---- 最長の道・最大の騎士 ----
    def road_length(self, p: int) -> int:
        mine = {e for e in range(N_EDGE) if self.road[e] == p}
        if not mine:
            return 0

        def blocked(v: int) -> bool:
            return self.building[v] not in (-1, p)

        def dfs(v: int, used: set[int]) -> int:
            best = 0
            for e in TOPO.vertex_edges[v]:
                if e in mine and e not in used:
                    a, b = TOPO.edges[e]
                    u = b if a == v else a
                    used.add(e)
                    length = 1 + (0 if blocked(u) else dfs(u, used))
                    used.discard(e)
                    best = max(best, length)
            return best

        starts = {v for e in mine for v in TOPO.edges[e]}
        return max(dfs(v, set()) for v in starts)

    def _update_longest(self) -> None:
        self.longest_len = [self.road_length(q) for q in range(self.n)]
        best = max(self.longest_len)
        h = self.longest_holder
        if best < LONGEST_MIN:
            self.longest_holder = None
        elif h is not None and self.longest_len[h] == best:
            pass  # 同点なら今の持ち主のまま
        else:
            top = [q for q in range(self.n) if self.longest_len[q] == best]
            self.longest_holder = top[0] if len(top) == 1 else None

    def _update_army(self) -> None:
        p = self.current
        k = self.players[p].knights
        h = self.army_holder
        if k >= ARMY_MIN and (h is None or k > self.players[h].knights):
            self.army_holder = p

    def _check_win(self) -> None:
        if self.phase in (SETUP_SETTLE, SETUP_ROAD):
            return
        if self.vp(self.current) >= WIN_VP:
            self.winner = self.current
            self.phase = OVER
