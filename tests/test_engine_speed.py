"""R-001: 速くしたエンジンが、速くする前の版（tests/ref_game_v0.py）と全く同じに動くか。

同じ seed のランダム対局を両方で打ち、毎手の「打てる手の一覧」（並び順も）と、
終局の勝者・手番数・盤面・手札が一致することを確かめる。
"""

from __future__ import annotations

import random

import pytest
import ref_game_v0

from isle.game import Game


def _state(g) -> tuple:
    return (
        g.phase,
        g.current,
        g.winner,
        g.turns,
        tuple(g.building),
        tuple(g.is_city),
        tuple(g.road),
        tuple(g.bank),
        tuple(tuple(pl.hand) for pl in g.players),
        tuple(tuple(pl.dev) for pl in g.players),
        g.longest_holder,
        tuple(g.longest_len),
        g.army_holder,
        g.robber,
    )


def _play_both(seed: int) -> int:
    new, old = Game(seed=seed), ref_game_v0.Game(seed=seed)
    rng = random.Random(seed)
    steps = 0
    while not new.is_over():
        acts = new.legal_actions()
        assert acts == old.legal_actions(), f"seed {seed} 手 {steps}: 打てる手が違う"
        a = rng.choice(acts)
        new.apply(a)
        old.apply(a)
        steps += 1
        if steps % 50 == 0:
            assert _state(new) == _state(old), f"seed {seed} 手 {steps}: 局面が違う"
            # 写しも元と同じに続くか（探索で使う）
            c = new.clone()
            assert _state(c) == _state(new)
            assert c.legal_actions() == new.legal_actions()
    assert old.is_over()
    assert _state(new) == _state(old), f"seed {seed}: 終局が違う"
    return new.winner if new.winner is not None else -1


def test_fast_engine_matches_reference_quick():
    for seed in range(20):
        _play_both(seed)


@pytest.mark.slow
def test_fast_engine_matches_reference_500_games():
    winners = [_play_both(seed) for seed in range(500)]
    assert len(winners) == 500
