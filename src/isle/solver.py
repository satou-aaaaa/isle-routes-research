"""手番の中を読み切る小さな厳密ソルバー。

サイコロを振ったあとの手番の中では、発展カードを買う・盗む以外の手に運がない。
そこで「この手番のうちに10点に届く手順があるか」を全部の手順を調べて確かめる。
4人のゲームに一つに決まる「理論上の最善」はないが、「勝てる手番を逃さない」ことは
どの考え方でも正しい手なので、AIの悪手を測る物差しに使える。
"""

from __future__ import annotations

from .game import MAIN, OVER, ROBBER, STEAL, WIN_VP, Game

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
    c = s.clone()
    c.apply(a)
    return c._steal_targets() if c.phase == STEAL else []


def find_win(g: Game, max_nodes: int = 20000) -> list[tuple] | None:
    """今の手番のうちに勝てる手順を返す（なければ None）。g は変えない。"""
    if g.phase != MAIN:
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
        roads_ok = _road_could_matter(s, p)
        acts = s.legal_actions()
        if s.phase == ROBBER:
            # 盗賊の置き場は点数に関係しない。運の入らない（盗む相手のいない）所があればそこへ
            acts = sorted(acts, key=lambda a: bool(_targets_after(s, a)))[:1]
        elif s.phase == STEAL:
            acts = acts[:1]  # 盗むカードは運。ここを通る筋は確実ではない
        for a in acts:
            if a[0] in SKIP:
                continue
            if a[0] in ("build_road", "free_road", "road_building") and not roads_ok:
                continue
            c = s.clone()
            c.apply(a)
            r = dfs(c, path + [a])
            if r is not None:
                return r
        return None

    return dfs(g.clone(), [])
