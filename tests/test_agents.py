"""AI・対局の仕組みのテスト。"""

from __future__ import annotations

import random

import pytest

from isle.agents import GreedyAgent, RandomAgent, make_agent
from isle.arena import play_game, replay, run_rotated
from isle.features import DEFAULT_WEIGHTS, FEATURES, features
from isle.game import Game
from isle.models import load


def test_clone_is_independent():
    g = Game(seed=3)
    rng = random.Random(3)
    for _ in range(80):
        g.apply(rng.choice(g.legal_actions()))
    c = g.clone()
    before = (list(g.bank), [list(p.hand) for p in g.players], list(g.road), g.rng.getstate())
    rng2 = random.Random(4)
    for _ in range(50):
        if c.is_over():
            break
        c.apply(rng2.choice(c.legal_actions()))
    after = (list(g.bank), [list(p.hand) for p in g.players], list(g.road), g.rng.getstate())
    assert before == after


def test_clone_continues_the_same_way():
    g = Game(seed=5)
    rng = random.Random(5)
    for _ in range(40):
        g.apply(rng.choice(g.legal_actions()))
    c = g.clone()
    seq = [rng.choice(g.legal_actions())]
    g.apply(seq[0])
    c.apply(seq[0])
    assert g.last_roll == c.last_roll and g.players[0].hand == c.players[0].hand


def test_replay_reproduces_game():
    agents = [make_agent("greedy", seed=1)] + [RandomAgent(seed=s) for s in range(3)]
    rec = play_game(agents, seed=11)
    g = replay(rec)
    assert g.winner == rec["winner"]
    assert [g.vp(q) for q in range(4)] == rec["vp"]


def test_features_shape():
    g = Game(seed=1)
    assert len(features(g, 0)) == len(FEATURES) == len(DEFAULT_WEIGHTS)


def test_load_falls_back_to_hand_weights():
    assert load("does-not-exist") == DEFAULT_WEIGHTS


def test_greedy_ignores_dev_deck_order():
    """山札の並びを変えても、発展カードを買うかどうかの判断は変わらない（山札をのぞかない）。"""
    checked = 0
    for seed in range(30):
        g = Game(seed=seed)
        rng = random.Random(seed)
        while not g.is_over() and g.turns < 60:
            if g.to_act == 0 and ("buy_dev",) in g.legal_actions():
                choices = set()
                for order in range(3):
                    c = g.clone()
                    random.Random(order).shuffle(c.dev_deck)
                    choices.add(GreedyAgent(seed=0).act(c))
                assert len(choices) == 1
                checked += 1
                break
            g.apply(rng.choice(g.legal_actions()))
    assert checked >= 5


def test_rotated_counts():
    res = run_rotated(["greedy", "random", "random", "random"], make_agent, 1, seed=0)
    assert res["games"] == 4
    assert sum(res["seat_wins"]) == 4


@pytest.mark.slow
def test_greedy_beats_random():
    res = run_rotated(["greedy", "random", "random", "random"], make_agent, 10, seed=100)
    assert res["agents"]["greedy"]["win_rate"] > 0.8
