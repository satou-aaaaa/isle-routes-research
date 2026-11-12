"""ルールエンジンのテスト。数字は基本ルール（公式ルールブック 2015年版）の値。"""

from __future__ import annotations

import random

import pytest

from isle.board import (
    BRICK,
    DESERT,
    GENERIC,
    GRAIN,
    HEX_NEIGHBORS,
    N_EDGE,
    N_HEX,
    N_VERTEX,
    NUMBER_TOKENS,
    ORE,
    PORT_EDGES,
    TOPO,
    WOOD,
    WOOL,
    dice_ways,
    random_layout,
)
from isle.game import (
    BANK_EACH,
    DEV_DECK,
    DISCARD,
    KNIGHT,
    MAIN,
    MONOPOLY,
    OVER,
    PRE_ROLL,
    ROBBER,
    SETUP_ROAD,
    SETUP_SETTLE,
    VP_CARD,
    Game,
)


def play_random(seed: int) -> Game:
    g = Game(seed=seed)
    rng = random.Random(seed)
    while not g.is_over():
        g.apply(rng.choice(g.legal_actions()))
    return g


def finish_setup(g: Game, rng: random.Random) -> None:
    while g.phase in (SETUP_SETTLE, SETUP_ROAD):
        g.apply(rng.choice(g.legal_actions()))


def empty_main_game(seed: int = 0) -> Game:
    """初期配置を済ませ、手番0が振った後（MAIN）にした局面。手札は空にする。"""
    g = Game(seed=seed)
    finish_setup(g, random.Random(seed))
    for pl in g.players:
        for r in range(5):
            g.bank[r] += pl.hand[r]
        pl.hand = [0] * 5
    g.phase, g.rolled = MAIN, True
    return g


def give(g: Game, p: int, r: int, k: int) -> None:
    g.bank[r] -= k
    g.players[p].hand[r] += k


# ---- 盤面 ----
def test_board_shape():
    assert (N_HEX, N_VERTEX, N_EDGE) == (19, 54, 72)
    assert len(TOPO.coastal_edges) == 30
    assert all(len(vs) == 6 for vs in TOPO.hex_vertices)
    assert all(len(n) in (2, 3) for n in TOPO.vertex_neighbors)


def test_ports_do_not_share_vertices():
    vs = [v for e in PORT_EDGES for v in TOPO.edges[e]]
    assert len(vs) == len(set(vs)) == 18
    assert all(e in TOPO.coastal_edges for e in PORT_EDGES)


def test_layout_counts_and_red_numbers_apart():
    for s in range(50):
        lay = random_layout(random.Random(s))
        assert sorted(lay.terrain) == sorted(
            [WOOD] * 4 + [BRICK] * 3 + [WOOL] * 4 + [GRAIN] * 4 + [ORE] * 3 + [DESERT]
        )
        assert sorted(n for n in lay.number if n) == sorted(NUMBER_TOKENS)
        assert lay.number[lay.desert] == 0
        red = [h for h, n in enumerate(lay.number) if n in (6, 8)]
        assert all(not set(HEX_NEIGHBORS[h]) & set(red) for h in red)
        assert sorted(lay.ports).count(GENERIC) == 4


def test_dice_ways():
    assert sum(dice_ways(n) for n in range(2, 13)) == 36
    assert dice_ways(6) == dice_ways(8) == 5 and dice_ways(2) == dice_ways(12) == 1


def test_dev_deck():
    assert len(DEV_DECK) == 25
    assert DEV_DECK.count(KNIGHT) == 14 and DEV_DECK.count(VP_CARD) == 5


# ---- 初期配置 ----
def test_setup_snake_order_and_resources():
    g = Game(seed=1)
    rng = random.Random(1)
    order = []
    while g.phase in (SETUP_SETTLE, SETUP_ROAD):
        if g.phase == SETUP_SETTLE:
            order.append(g.current)
            before = list(g.players[g.current].hand)
            a = rng.choice(g.legal_actions())
            g.apply(a)
            got = sum(g.players[g.current].hand) - sum(before)
            expected = len(g.vertex_yield[a[1]]) if len(order) > 4 else 0
            assert got == expected
        else:
            g.apply(rng.choice(g.legal_actions()))
    assert order == [0, 1, 2, 3, 3, 2, 1, 0]
    assert g.phase == PRE_ROLL and g.current == 0
    assert all(p.settlements == 2 and p.roads == 2 for p in g.players)


def test_distance_rule():
    g = Game(seed=2)
    v = 10
    g.apply(("settle", v))
    g.apply(("road", TOPO.vertex_edges[v][0]))
    legal = {a[1] for a in g.legal_actions()}
    assert v not in legal
    assert not legal & set(TOPO.vertex_neighbors[v])


# ---- 産出・盗賊 ----
def test_production_city_robber():
    g = empty_main_game(3)
    h = next(h for h in range(N_HEX) if g.layout.number[h] not in (0,))
    r, n = g.layout.terrain[h], g.layout.number[h]
    # その六角形の頂点を全部空けて、手番0の都市を1つ置く
    for v in range(N_VERTEX):
        if v in TOPO.hex_vertices[h]:
            g.building[v] = -1
    v = TOPO.hex_vertices[h][0]
    g.building[v], g.is_city[v] = 0, True
    g.robber = g.layout.desert
    before = g.players[0].hand[r]
    g.produce(n)
    assert g.players[0].hand[r] - before >= 2
    g.robber = h
    before = g.players[0].hand[r]
    g.produce(n)
    gained_elsewhere = sum(
        (2 if g.is_city[u] else 1)
        for u in range(N_VERTEX)
        if g.building[u] == 0
        for hh, rr, nn in g.vertex_yield[u]
        if nn == n and rr == r and hh != h
    )
    assert g.players[0].hand[r] - before == gained_elsewhere


def test_bank_shortage_nobody_gets():
    g = empty_main_game(4)
    h = next(h for h in range(N_HEX) if g.layout.number[h])
    r, n = g.layout.terrain[h], g.layout.number[h]
    for v in range(N_VERTEX):
        g.building[v] = -1
    a, b = TOPO.hex_vertices[h][0], TOPO.hex_vertices[h][3]
    g.building[a], g.building[b] = 0, 1
    for pl in g.players:
        pl.hand = [0] * 5
    g.bank = [BANK_EACH] * 5
    g.bank[r] = 1
    g.produce(n)
    assert g.players[0].hand[r] == g.players[1].hand[r] == 0
    g.building[b] = -1
    g.is_city[a] = True
    g.produce(n)
    assert g.players[0].hand[r] == 1  # 1人だけなら残りをもらう


def test_seven_discard_then_robber():
    g = Game(seed=5)
    finish_setup(g, random.Random(5))
    g.players[1].hand = [3, 3, 3, 0, 0]  # 9枚 → 4枚捨てる
    g.players[2].hand = [7, 0, 0, 0, 0]  # 7枚 → 捨てない
    dice = iter([3, 4])  # 3 + 4 = 7
    g.rng.randint = lambda a, b: next(dice)
    g.apply(("roll",))
    assert g.last_roll == 7 and g.phase == DISCARD and g.to_act == 1
    for _ in range(4):
        g.apply(g.legal_actions()[0])
    assert g.players[1].cards() == 5
    assert g.phase == ROBBER


# ---- 建設・カード ----
def test_build_costs_and_city():
    g = empty_main_game(6)
    v = next(v for v in range(N_VERTEX) if g.building[v] == 0)
    give(g, 0, GRAIN, 2)
    give(g, 0, ORE, 3)
    assert ("build_city", v) in g.legal_actions()
    g.apply(("build_city", v))
    assert g.players[0].hand == [0] * 5 and g.players[0].cities == 1
    assert g.vp(0) == 3


def test_dev_card_not_playable_same_turn_and_one_per_turn():
    g = empty_main_game(7)
    g.dev_deck.append(KNIGHT)
    give(g, 0, WOOL, 1)
    give(g, 0, GRAIN, 1)
    give(g, 0, ORE, 1)
    g.apply(("buy_dev",))
    assert ("knight",) not in g.legal_actions()
    g.players[0].dev[MONOPOLY] += 1  # 前の手番から持っていた分
    assert ("monopoly", WOOD) in g.legal_actions()
    g.apply(("monopoly", WOOD))
    assert not any(a[0] in ("knight", "monopoly") for a in g.legal_actions())


def test_bank_and_port_ratios():
    g = empty_main_game(8)
    give(g, 0, WOOD, 4)
    assert ("trade", WOOD, ORE) in g.legal_actions()
    give(g, 0, WOOD, -1)
    assert ("trade", WOOD, ORE) not in g.legal_actions()
    port_v = next(v for v, k in g.vertex_port.items() if k == WOOD)
    g.building[port_v] = 0
    give(g, 0, WOOD, -1)  # 2枚
    assert g._trade_ratio(0, WOOD) == 2
    g.apply(("trade", WOOD, ORE))
    assert g.players[0].hand[WOOD] == 0 and g.players[0].hand[ORE] == 1


def test_longest_road_and_break():
    g = Game(seed=9)
    # 一直線に6本の道を手番0に置く（外周の辺を順にたどる）
    path = []
    v = TOPO.edges[TOPO.coastal_edges[0]][0]
    used = set()
    for _ in range(6):
        e = next(e for e in TOPO.vertex_edges[v] if e in TOPO.coastal_edges and e not in used)
        used.add(e)
        path.append(e)
        a, b = TOPO.edges[e]
        v = b if a == v else a
    for e in path:
        g.road[e] = 0
    g._update_longest()
    assert g.road_length(0) == 6 and g.longest_holder == 0
    # 真ん中の頂点に相手の開拓地 → 3本ずつに分かれる
    a, b = TOPO.edges[path[2]]
    mid = next(x for x in (a, b) if x in TOPO.edges[path[3]])
    g.building[mid] = 1
    g._update_longest()
    assert g.road_length(0) == 3 and g.longest_holder is None


def test_largest_army():
    g = empty_main_game(10)
    g.players[0].knights = 2
    g.players[0].dev[KNIGHT] = 1
    g.apply(("knight",))
    assert g.army_holder == 0 and g.phase == ROBBER


# ---- 通しの対局 ----
@pytest.mark.parametrize("seed", range(40))
def test_random_games_keep_invariants(seed):
    g = play_random(seed)
    assert g.phase == OVER and g.winner is not None
    assert g.vp(g.winner) >= 10
    for r in range(5):
        assert g.bank[r] + sum(p.hand[r] for p in g.players) == BANK_EACH
    for q, p in enumerate(g.players):
        assert 0 <= p.settlements <= 5 and 0 <= p.cities <= 4 and 0 <= p.roads <= 15
        assert p.roads == g.road.count(q)
        assert p.settlements + p.cities == g.building.count(q)
    dev_total = len(g.dev_deck) + sum(sum(p.dev) + p.knights for p in g.players)
    assert dev_total <= 25
