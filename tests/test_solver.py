"""手番の中の厳密ソルバーのテスト。"""

from __future__ import annotations

import random

from isle.board import GRAIN, N_VERTEX, ORE
from isle.game import MAIN, SETUP_ROAD, SETUP_SETTLE, Game
from isle.solver import find_win


def main_game(seed: int) -> Game:
    g = Game(seed=seed)
    rng = random.Random(seed)
    while g.phase in (SETUP_SETTLE, SETUP_ROAD):
        g.apply(rng.choice(g.legal_actions()))
    for pl in g.players:
        for r in range(5):
            g.bank[r] += pl.hand[r]
        pl.hand = [0] * 5
    g.phase, g.rolled = MAIN, True
    return g


def nine_points(g: Game) -> None:
    """手番0を村2つ・街…で9点にする（手で盤を書きかえる）。"""
    mine = [v for v in range(N_VERTEX) if g.building[v] == 0]
    for v in mine:
        g.is_city[v] = True
    pl = g.players[0]
    pl.settlements, pl.cities = 0, 2
    pl.dev[1] = 5  # 得点カード5枚 → 4 + 5 = 9点


def test_finds_city_win_and_line_wins():
    g = main_game(1)
    nine_points(g)
    g.is_city[[v for v in range(N_VERTEX) if g.building[v] == 0][0]] = False
    g.players[0].settlements, g.players[0].cities = 1, 1  # 1 + 2 + 5 = 8点
    g.players[0].dev[1] = 6  # 9点
    assert g.vp(0) == 9
    g.bank[GRAIN] -= 2
    g.bank[ORE] -= 3
    g.players[0].hand = [0, 0, 0, 2, 3]
    line = find_win(g)
    assert line and line[-1][0] == "build_city"
    c = g.clone()
    for a in line:
        c.apply(a)
    assert c.winner == 0


def test_finds_win_through_bank_trade():
    g = main_game(2)
    nine_points(g)
    g.players[0].settlements, g.players[0].cities = 1, 1
    g.is_city[[v for v in range(N_VERTEX) if g.building[v] == 0][0]] = False
    g.players[0].dev[1] = 6
    g.vertex_port = {}  # 港なし（4:1 だけ）
    hand = [0, 0, 8, 2, 1]  # 羊毛8枚を鉱石2枚に替えれば街を建てられる
    for r in range(5):
        g.bank[r] -= hand[r]
    g.players[0].hand = list(hand)
    line = find_win(g)
    assert line is not None
    assert sum(1 for a in line if a[0] == "trade") == 2
    g.players[0].hand[2] = 7  # 羊毛が1枚足りない
    g.bank[2] += 1
    assert find_win(g) is None


def test_no_win_when_far_from_ten():
    g = main_game(3)
    g.players[0].hand = [4, 4, 4, 4, 4]
    for r in range(5):
        g.bank[r] -= 4
    assert find_win(g) is None


def test_does_not_change_state():
    g = main_game(4)
    before = (list(g.building), list(g.road), [list(p.hand) for p in g.players])
    find_win(g)
    assert before == (list(g.building), list(g.road), [list(p.hand) for p in g.players])
