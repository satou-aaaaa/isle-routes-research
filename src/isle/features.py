"""盤面の特徴量と評価関数。

評価値は「その人がどれだけ勝ちに近いか」の目安。重みは最初は手で決め、のちに自己対戦で学ぶ。
特徴量の名前は FEATURES の順。学習した重みは同じ順の配列で渡す。
"""

from __future__ import annotations

from .board import N_VERTEX, RESOURCES, dice_ways
from .game import (
    COST,
    MAX_CITIES,
    MAX_SETTLEMENTS,
    VP_CARD,
    Game,
)

FEATURES = (
    "vp",  # 点数（自分には得点カードも見える）
    "prod_total",  # 1回のサイコロで期待できる資源の枚数
    "prod_wood",
    "prod_brick",
    "prod_wool",
    "prod_grain",
    "prod_ore",
    "prod_kinds",  # 産出する資源の種類数
    "port_generic",  # 3:1 の港を持つ
    "port_match",  # 2:1 の港の資源を自分も産出している（その産出量）
    "spots",  # 自分の道からすぐ建てられる空き頂点の数（上限3）
    "spot_value",  # その中で一番よい頂点の産出
    "road_len",  # 最長の道の長さ（上限8）
    "knights",  # 使った騎士（上限5）
    "dev_hidden",  # 手元の発展カード（得点カード以外）
    "cards",  # 手札の枚数（上限7）
    "over7",  # 8枚以上のときの超えた分
    "afford_settlement",  # 村を建てられる手札
    "afford_city",  # 街を建てられる手札
    "afford_dev",  # 発展カードを買える手札
    "near_city",  # 街までの不足枚数の少なさ（0〜1）
    "near_settlement",  # 村までの不足枚数の少なさ（0〜1）
    "robbed",  # 盗賊に止められている産出
)
F = {name: i for i, name in enumerate(FEATURES)}

# 手で決めた最初の重み（点数1点 = 1.0 の目盛り）
HAND_WEIGHTS = {
    "vp": 1.0,
    "prod_total": 1.6,
    "prod_wood": 0.5,
    "prod_brick": 0.5,
    "prod_wool": 0.2,
    "prod_grain": 0.6,
    "prod_ore": 0.6,
    "prod_kinds": 0.15,
    "port_generic": 0.15,
    "port_match": 0.8,
    "spots": 0.15,
    "spot_value": 0.6,
    "road_len": 0.05,
    "knights": 0.15,
    "dev_hidden": 0.35,
    "cards": 0.05,
    "over7": -0.12,
    "afford_settlement": 0.4,
    "afford_city": 0.5,
    "afford_dev": 0.15,
    "near_city": 0.25,
    "near_settlement": 0.25,
    "robbed": -0.6,
}
DEFAULT_WEIGHTS = tuple(HAND_WEIGHTS.get(name, 0.0) for name in FEATURES)


def vertex_production(g: Game, v: int, robber_ok: bool = True) -> list[float]:
    """頂点 v に村があるとき、1回のサイコロで期待できる資源（種類ごと）。"""
    out = [0.0] * 5
    for h, r, num in g.vertex_yield[v]:
        if robber_ok and h == g.robber:
            continue
        out[r] += dice_ways(num) / 36
    return out


def _shortfall(hand: list[int], cost) -> int:
    return sum(max(0, c - h) for h, c in zip(hand, cost, strict=True))


def features(g: Game, p: int) -> list[float]:
    pl = g.players[p]
    f = [0.0] * len(FEATURES)
    f[F["vp"]] = g.vp(p)
    prod = [0.0] * 5
    robbed = 0.0
    generic = False
    ports: set[int] = set()
    for v in range(N_VERTEX):
        if g.building[v] != p:
            continue
        k = 2 if g.is_city[v] else 1
        for h, r, num in g.vertex_yield[v]:
            amount = k * dice_ways(num) / 36
            if h == g.robber:
                robbed += amount
            else:
                prod[r] += amount
        kind = g.vertex_port.get(v)
        if kind is not None:
            if kind in RESOURCES:
                ports.add(kind)
            else:
                generic = True
    f[F["prod_total"]] = sum(prod)
    for r, name in enumerate(("prod_wood", "prod_brick", "prod_wool", "prod_grain", "prod_ore")):
        f[F[name]] = prod[r]
    f[F["prod_kinds"]] = sum(1 for x in prod if x > 0)
    f[F["port_generic"]] = 1.0 if generic else 0.0
    f[F["port_match"]] = sum(prod[r] for r in ports)
    f[F["robbed"]] = robbed

    # すぐ建てられる空き頂点
    spot_vals = []
    if pl.settlements < MAX_SETTLEMENTS:
        for v in range(N_VERTEX):
            if g.building[v] == -1 and g._vertex_free(v) and g._touches_own_road(p, v):
                spot_vals.append(sum(vertex_production(g, v)))
    f[F["spots"]] = min(3, len(spot_vals))
    f[F["spot_value"]] = max(spot_vals, default=0.0)

    f[F["road_len"]] = min(8, g.longest_len[p])
    f[F["knights"]] = min(5, pl.knights)
    f[F["dev_hidden"]] = sum(pl.dev) - pl.dev[VP_CARD]
    n = sum(pl.hand)
    f[F["cards"]] = min(7, n)
    f[F["over7"]] = max(0, n - 7)
    can_settle = bool(spot_vals) and _shortfall(pl.hand, COST["settlement"]) == 0
    can_city = (
        pl.cities < MAX_CITIES and pl.settlements > 0 and _shortfall(pl.hand, COST["city"]) == 0
    )
    f[F["afford_settlement"]] = 1.0 if can_settle else 0.0
    f[F["afford_city"]] = 1.0 if can_city else 0.0
    f[F["afford_dev"]] = 1.0 if g.dev_deck and _shortfall(pl.hand, COST["dev"]) == 0 else 0.0
    f[F["near_city"]] = 1 - _shortfall(pl.hand, COST["city"]) / 5
    f[F["near_settlement"]] = 1 - _shortfall(pl.hand, COST["settlement"]) / 4
    return f


def evaluate(g: Game, p: int, weights=DEFAULT_WEIGHTS) -> float:
    if g.winner is not None:
        return 100.0 if g.winner == p else -100.0
    return sum(w * x for w, x in zip(weights, features(g, p), strict=True))
