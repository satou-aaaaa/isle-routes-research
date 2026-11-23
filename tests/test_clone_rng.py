"""R-006: 探索用の写しに新しい乱数を渡す形（clone(rng=...)）のテスト。"""

from __future__ import annotations

import random
import timeit

from test_engine_speed import _state

from isle.game import Game


def _midgame(seed: int, steps: int = 300) -> Game:
    g = Game(seed=seed)
    rng = random.Random(seed)
    for _ in range(steps):
        if g.is_over():
            break
        g.apply(rng.choice(g.legal_actions()))
    return g


def _play_out(g: Game, seed: int) -> tuple:
    rng = random.Random(seed)
    while not g.is_over():
        g.apply(rng.choice(g.legal_actions()))
    return _state(g)


def test_clone_with_rng_copies_the_board_but_not_the_rng():
    g = _midgame(1)
    before = g.rng.getstate()
    r = random.Random(5)
    c = g.clone(rng=r)
    assert c.rng is r
    assert _state(c) == _state(g)
    assert c.legal_actions() == g.legal_actions()
    # 写しを最後まで打っても、元の局面と乱数は変わらない
    _play_out(c, 9)
    assert g.rng.getstate() == before
    assert not g.is_over()


def test_same_seed_gives_the_same_future():
    g = _midgame(2)
    a = _play_out(g.clone(rng=123), 7)
    b = _play_out(g.clone(rng=random.Random(123)), 7)
    assert a == b
    others = {_play_out(g.clone(rng=s), 7) for s in range(8)}
    assert len(others) > 1  # seed を変えると先の出目が変わる


def test_default_clone_still_follows_the_original():
    g = _midgame(3)
    c = g.clone()
    assert _play_out(c, 11) == _play_out(g, 11)


def test_clone_with_rng_is_at_least_twice_as_fast():
    g = _midgame(4)
    r = random.Random(0)
    full = min(timeit.repeat(g.clone, number=2000, repeat=5))
    fast = min(timeit.repeat(lambda: g.clone(rng=r), number=2000, repeat=5))
    assert fast < full / 2, (full, fast)
