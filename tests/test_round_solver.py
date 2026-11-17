"""終盤1巡の読み切り（round_solver）と、それを速くする部品のテスト。"""

from __future__ import annotations

import time

import pytest

from isle.agents import make_agent
from isle.game import MAIN, Game
from isle.round_solver import MAXN, PARANOID, RoundSolver, TooBig, agent_chooser
from isle.solver import could_win, find_win


def _main_positions(games: int, min_vp: int, seed: int = 900):
    """greedy_win どうしの対局から、サイコロのあと最初の手の局面を集める。"""
    out = []
    for i in range(games):
        g = Game(seed=seed + i)
        agents = [make_agent("greedy_win", seed=(seed + i) * 10 + j) for j in range(4)]
        last = -1
        while not g.is_over():
            if g.phase == MAIN and g.turns != last:
                last = g.turns
                if max(g.vp(q) for q in range(4)) >= min_vp:
                    out.append(g.clone())
            g.apply(agents[g.to_act].act(g))
    return out


def test_no_rng_clone_refuses_rng():
    g = Game(seed=1)
    c = g.clone(keep_rng=False)
    with pytest.raises(RuntimeError):
        c.rng.random()


def test_could_win_never_hides_a_win():
    """could_win は甘めの上限: 実際に勝ち筋がある局面で False を返さない。"""
    positions = _main_positions(6, min_vp=7)
    wins = 0
    for g in positions:
        found = find_win(g, bound=False) is not None
        if found:
            wins += 1
            assert could_win(g)
        assert (find_win(g) is not None) == found
    assert wins > 0


def _small_positions():
    """R-002 の測定（seed 800037）で、数秒で読み切れて値が0でなかった2局面。"""
    out = []
    g = Game(seed=800037)
    agents = [make_agent("greedy_win", seed=800037 * 10 + j) for j in range(4)]
    last = -1
    while not g.is_over() and g.turns <= 40:
        if g.phase == MAIN and g.turns != last:
            last = g.turns
            if g.turns in (36, 40):
                out.append(g.clone())
        g.apply(agents[g.to_act].act(g))
    return out


def test_round_values_are_consistent():
    positions = _small_positions()
    assert len(positions) == 2
    for g in positions:
        vals = {}
        for mode in (MAXN, PARANOID):
            rs = RoundSolver(g.current, mode, max_seconds=60)
            v = rs.value(g.clone())
            assert 0.0 < v <= 1.0
            if find_win(g):
                assert v == 1.0
            for name in ("greedy", "greedy_win"):
                va = rs.agent_value(g.clone(), agent_chooser(make_agent(name, seed=1)))
                assert -1e-9 <= va <= v + 1e-9  # 最善より良くはならない
            vals[mode] = v
        # paranoid の相手は max^n の相手の選び方も候補に入れて最悪を選ぶので、値は大きくならない
        assert vals[PARANOID] <= vals[MAXN] + 1e-9


def test_time_limit_stops_the_search():
    """時間の上限は、1つの終わり方の先を読んでいる途中でも効く（CI や測定が止まらなくならない）。"""
    g = next(x for x in _main_positions(4, min_vp=8, seed=950) if x.vp(x.current) >= 7)
    t = time.monotonic()
    with pytest.raises(TooBig):
        RoundSolver(g.current, MAXN, max_seconds=1).value(g.clone())
    assert time.monotonic() - t < 15
