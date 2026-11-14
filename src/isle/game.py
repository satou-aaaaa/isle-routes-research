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

# 速さのための表（盤の形だけで決まる）
# 頂点ごとの (辺, 辺の向こうの頂点)
_VERTEX_STEPS = tuple(
    tuple((e, TOPO.edges[e][1] if TOPO.edges[e][0] == v else TOPO.edges[e][0]) for e in es)
    for v, es in enumerate(TOPO.vertex_edges)
)
# 辺ごとに、両端の頂点と「その頂点に接するほかの辺」
_EDGE_ENDS = tuple(
    tuple((v, tuple(f for f in TOPO.vertex_edges[v] if f != e)) for v in TOPO.edges[e])
    for e in range(N_EDGE)
)

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

    def copy(self) -> Player:
        c = Player.__new__(Player)
        c.__dict__.update(self.__dict__)
        c.hand = self.hand[:]
        c.dev = self.dev[:]
        c.dev_new = self.dev_new[:]
        return c


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
        self.longest_fresh = False  # longest_len が全員ぶん今の盤と合っているか
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
        # 出目ごとの (頂点, 六角形, 資源)。produce() で全頂点を見ないため
        self.number_yield: list[list[tuple[int, int, int]]] = [[] for _ in range(13)]
        for v in range(N_VERTEX):
            for h, r, num in self.vertex_yield[v]:
                self.number_yield[num].append((v, h, r))

    # ---- 便利関数 ----
    def clone(self) -> Game:
        """探索用の写し。盤面の並べ方など変わらないものは共有し、変わるものだけ写す。"""
        g = Game.__new__(Game)
        g.__dict__.update(self.__dict__)
        g.rng = random.Random()
        g.rng.setstate(self.rng.getstate())
        g.players = [pl.copy() for pl in self.players]
        g.bank = list(self.bank)
        g.dev_deck = list(self.dev_deck)
        g.building = list(self.building)
        g.is_city = list(self.is_city)
        g.road = list(self.road)
        g.longest_len = list(self.longest_len)
        g.discard_queue = list(self.discard_queue)
        return g

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
        road = self.road
        if road[e] != -1:
            return False
        building = self.building
        for v, others in _EDGE_ENDS[e]:
            owner = building[v]
            if owner == p:
                return True
            if owner != -1:
                continue  # 他人の建物の先にはつながらない
            for f in others:
                if road[f] == p:
                    return True
        return False

    def _road_spots(self, p: int) -> list[int]:
        """p が道を置ける辺（番号の小さい順）。"""
        road, building = self.road, self.building
        out = []
        for e in range(N_EDGE):
            if road[e] != -1:
                continue
            for v, others in _EDGE_ENDS[e]:
                owner = building[v]
                if owner == p:
                    out.append(e)
                    break
                if owner != -1:
                    continue
                if road[others[0]] == p or (len(others) > 1 and road[others[1]] == p):
                    out.append(e)
                    break
        return out

    def _trade_ratios(self, p: int) -> list[int]:
        """資源ごとの交換の比（_trade_ratio を5資源まとめて）。"""
        out = [4] * 5
        generic = False
        building = self.building
        for v, kind in self.vertex_port.items():
            if building[v] == p:
                if kind == GENERIC:
                    generic = True
                else:
                    out[kind] = 2
        if generic:
            out = [min(x, 3) for x in out]
        return out

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
            return [("free_road", e) for e in self._road_spots(p)]
        # MAIN（費用の確かめは COST と同じ中身を手で書いて速くしている）
        acts: list[tuple] = [("end",)]
        wood, brick, wool, grain, ore = pl.hand
        building = self.building
        if pl.roads < MAX_ROADS and wood and brick:
            acts += [("build_road", e) for e in self._road_spots(p)]
        if pl.settlements < MAX_SETTLEMENTS and wood and brick and wool and grain:
            road = self.road
            neighbors = TOPO.vertex_neighbors
            vedges = TOPO.vertex_edges
            for v in range(N_VERTEX):
                if building[v] != -1:
                    continue
                if any(building[u] != -1 for u in neighbors[v]):
                    continue
                if any(road[e] == p for e in vedges[v]):
                    acts.append(("build_settlement", v))
        if pl.cities < MAX_CITIES and grain >= 2 and ore >= 3:
            is_city = self.is_city
            acts += [
                ("build_city", v) for v in range(N_VERTEX) if building[v] == p and not is_city[v]
            ]
        if self.dev_deck and wool and grain and ore:
            acts.append(("buy_dev",))
        if not self.dev_played and any(pl.dev):
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
        hand = pl.hand
        if max(hand) >= 2:
            ratios = self._trade_ratios(p)
            bank = self.bank
            for give in RESOURCES:
                if hand[give] >= ratios[give]:
                    acts += [
                        ("trade", give, get) for get in RESOURCES if get != give and bank[get] > 0
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
            self._update_longest(p)
        elif kind == "free_road":
            self.road[a[1]] = p
            pl.roads += 1
            self.free_roads -= 1
            self._update_longest(p)
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
        total = [0] * 5
        building, is_city, robber = self.building, self.is_city, self.robber
        for v, h, r in self.number_yield[d]:
            q = building[v]
            if q == -1 or h == robber:
                continue
            k = 2 if is_city[v] else 1
            want[q][r] += k
            total[r] += k
        for r in RESOURCES:
            if total[r] == 0:
                continue
            takers = [q for q in range(self.n) if want[q][r]]
            if total[r] <= self.bank[r]:
                for q in takers:
                    self._take_from_bank(q, r, want[q][r])
            elif len(takers) == 1:
                self._take_from_bank(takers[0], r, self.bank[r])

    # ---- 最長の道・最大の騎士 ----
    def road_length(self, p: int) -> int:
        road, building = self.road, self.building
        mine = [e for e in range(N_EDGE) if road[e] == p]
        if not mine:
            return 0
        used = [False] * N_EDGE

        def dfs(v: int) -> int:
            best = 0
            for e, u in _VERTEX_STEPS[v]:
                if road[e] == p and not used[e]:
                    used[e] = True
                    owner = building[u]
                    length = 1 if owner != -1 and owner != p else 1 + dfs(u)
                    used[e] = False
                    if length > best:
                        best = length
            return best

        # 自分の道が触れている頂点すべてから数えて最大をとる（前の版と同じ数え方）
        best = 0
        seen = [False] * N_VERTEX
        for e in mine:
            for v in TOPO.edges[e]:
                if not seen[v]:
                    seen[v] = True
                    d = dfs(v)
                    if d > best:
                        best = d
        return best

    def _update_longest(self, only: int | None = None) -> None:
        """最長の道を数え直す。only を渡すと、その人の長さだけ数え直す（ほかは変わらないとき）。"""
        if only is None or not self.longest_fresh:
            self.longest_len = [self.road_length(q) for q in range(self.n)]
            # 初期配置の道は数え直さないので、最初の1回は全員を数える（前の版と同じ値にするため）
            self.longest_fresh = True
        else:
            self.longest_len[only] = self.road_length(only)
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
