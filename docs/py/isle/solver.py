"""手番の中を読み切る小さな厳密ソルバー。

サイコロを振ったあとの手番の中では、発展カードを買う・盗む以外の手に運がない。
そこで「この手番のうちに10点に届く手順があるか」を全部の手順を調べて確かめる。
4人のゲームに一つに決まる「理論上の最善」はないが、「勝てる手番を逃さない」ことは
どの考え方でも正しい手なので、AIの悪手を測る物差しに使える。
"""

from __future__ import annotations

from .board import TOPO
from .game import (
    KNIGHT,
    LONGEST_MIN,
    MAIN,
    MAX_CITIES,
    MAX_SETTLEMENTS,
    MONOPOLY,
    OVER,
    PLENTY,
    ROAD_BUILDING,
    ROBBER,
    STEAL,
    WIN_VP,
    Game,
)

# 点数に関係しない・運が入る手は調べない
SKIP = {"end", "buy_dev"}


def _key(g: Game) -> tuple:
    return (
        tuple(g.players[g.current].hand),
        tuple(g.players[g.current].dev),
        tuple(g.building),
        tuple(g.is_city),
        tuple(g.road),
        g.dev_played,
        g.phase,
        g.robber,
    )


def _road_could_matter(g: Game, p: int) -> bool:
    """最長の道を取れば10点に届くときだけ、道を延ばす手を調べる。"""
    if g.longest_holder == p:
        return False
    return g.vp(p) + 2 >= WIN_VP


def _targets_after(s: Game, a: tuple) -> list[int]:
    c = s.clone(keep_rng=False)
    c.apply(a)
    return c._steal_targets() if c.phase == STEAL else []


def _build_vp(costs: list[int], cards: int) -> int:
    """手札 cards 枚で買える点の数の上限（安い順に買う）。"""
    n = 0
    for c in costs:
        if c > cards:
            break
        cards -= c
        n += 1
    return n


def could_win(g: Game, p: int | None = None, extra_cards: int = 0) -> bool:
    """この手番で10点に届く見込みが少しでもあるか（甘めの上限。False なら必ず届かない）。

    p を渡すと、その人の次の手番（発展カードは全部使える）について、手札が extra_cards 枚
    増えたとして見積もる（1巡先の見込みに使う）。

    村は4枚（今の道から建てられる空き頂点がなければ道の分も入れて6枚以上）、街は5枚で1点。
    交換は枚数を減らすだけ。最長の道（2点）は道1本2枚。
    発展カードは1手番1枚なので、増える手札は豊作2枚・独占（相手の持つ1種類の合計）・騎士で盗む1枚の大きい方。
    """
    if p is None or p == g.current:
        p = g.current
        pl = g.players[p]
        usable = [] if g.dev_played else [c for c in range(5) if pl.dev[c] - pl.dev_new[c] > 0]
    else:
        pl = g.players[p]
        usable = [c for c in range(5) if pl.dev[c] > 0]
    need = WIN_VP - g.vp(p)
    if need <= 0:
        return True
    extra = 0
    if PLENTY in usable:
        extra = 2
    if MONOPOLY in usable:
        extra = max(
            extra, max(sum(o.hand[r] for q, o in enumerate(g.players) if q != p) for r in range(5))
        )
    if KNIGHT in usable:
        extra = max(extra, 1)
    cards = pl.cards() + extra + extra_cards
    army = 0
    if KNIGHT in usable and g.army_holder != p:
        h = g.army_holder
        k = pl.knights + 1
        if k >= 3 and (h is None or k > g.players[h].knights):
            army = 2
    road_short = None  # 最長の道を取るのに足りない本数（取れないなら None）
    if g.longest_holder != p:
        free = 2 if ROAD_BUILDING in usable else 0
        length = g.longest_len[p] if g.longest_fresh else g.road_length(p)
        short = max(0, LONGEST_MIN - length - free)
        if short * 2 <= cards:
            road_short = short
    # まず空き頂点を数えずに甘く見積もる（ほとんどの局面はここで落ちる）
    rough = cards // 4 + army + (2 if road_short is not None else 0)
    if rough < need:
        return False
    s_left = MAX_SETTLEMENTS - pl.settlements
    spots = 0
    if s_left and cards >= 4:
        building, road = g.building, g.road
        for v in range(len(building)):
            if (
                building[v] == -1
                and any(road[e] == p for e in TOPO.vertex_edges[v])
                and all(building[u] == -1 for u in TOPO.vertex_neighbors[v])
            ):
                spots += 1
    now = min(spots, s_left)
    cities = min(MAX_CITIES - pl.cities, pl.settlements + s_left)
    costs = sorted([4] * now + [6] * (s_left - now) + [5] * cities)
    gain = _build_vp(costs, cards)
    if road_short is not None:
        gain = max(gain, 2 + _build_vp(costs, cards - 2 * road_short))
    return gain + army >= need


def find_win(g: Game, max_nodes: int = 20000, bound: bool = True) -> list[tuple] | None:
    """今の手番のうちに勝てる手順を返す（なければ None）。g は変えない。

    bound=True なら、could_win で届かないと分かる局面は調べずに None を返す（結果は同じで速い）。
    """
    if g.phase != MAIN:
        return None
    if bound and not could_win(g):
        return None
    p = g.current
    seen: set[tuple] = set()
    nodes = 0

    def dfs(s: Game, path: list[tuple]) -> list[tuple] | None:
        nonlocal nodes
        if s.phase == OVER:
            return path if s.winner == p else None
        if s.current != p or nodes >= max_nodes:
            return None
        k = _key(s)
        if k in seen:
            return None
        seen.add(k)
        nodes += 1
        if bound and s.phase == MAIN and not could_win(s):
            return None  # ここから先は届かない
        roads_ok = _road_could_matter(s, p)
        acts = s.legal_actions()
        if s.phase == ROBBER:
            # 盗賊の置き場は点数に関係しない。運の入らない（盗む相手のいない）所があればそこへ
            acts = sorted(acts, key=lambda a: bool(_targets_after(s, a)))[:1]
        elif s.phase == STEAL:
            return None  # 盗むカードは運。ここを通る筋は確実ではないので調べない
        for a in acts:
            if a[0] in SKIP:
                continue
            if a[0] in ("build_road", "free_road", "road_building") and not roads_ok:
                continue
            c = s.clone(keep_rng=False)  # 運の入る手（買う・盗む）は通らないので乱数は要らない
            c.apply(a)
            r = dfs(c, path + [a])
            if r is not None:
                return r
        return None

    return dfs(g.clone(keep_rng=False), [])
