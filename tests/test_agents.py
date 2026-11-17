"""AI・対局の仕組みのテスト。"""

from __future__ import annotations

import random

import pytest

from isle.agents import GreedyAgent, RandomAgent, WinCheckAgent, dev_vp_share, make_agent
from isle.arena import play_game, replay, run_rotated
from isle.features import DEFAULT_WEIGHTS, FEATURES, features
from isle.game import MAIN, VP_CARD, Game
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


def _main_phase_game(seed: int) -> Game:
    g = Game(seed=seed)
    rng = random.Random(seed)
    while not (g.phase == MAIN and g.current == 0 and g.turns >= 8):
        g.apply(rng.choice(g.legal_actions()))
    return g


def test_dev_vp_share_counts_unseen_cards():
    """得点カードの確率は「見えない札（山＋相手の手元）」の中の割合（R-007）。"""
    g = Game(seed=1)
    assert dev_vp_share(g, 0) == pytest.approx(5 / 25)
    # 自分が得点カードを2枚、相手が3枚の発展カードを持ち、山が10枚
    g.players[0].dev[VP_CARD] = 2
    g.players[1].dev[0] = 3
    g.dev_deck = g.dev_deck[:10]
    assert dev_vp_share(g, 0) == pytest.approx(3 / 13)
    g.players[0].dev[VP_CARD] = 5
    assert dev_vp_share(g, 0) == 0.0


def _at_nine(g: Game, hand) -> Game:
    pl = g.players[0]
    pl.settlements, pl.cities = 1, 4  # 9点（盤の上の形は使わない）
    g.longest_holder = g.army_holder = None
    pl.dev = [0] * 5
    pl.hand = list(hand)
    return g


def test_buys_dev_when_one_point_from_winning():
    """9点で発展カードを買えるなら、手番を終えずに買う（引けばその場で勝ち）。"""
    for seed in range(5):
        g = _at_nine(_main_phase_game(seed), (0, 0, 1, 1, 1))
        assert ("buy_dev",) in g.legal_actions()
        for agent in (GreedyAgent(seed=0), WinCheckAgent(seed=0)):
            assert agent.act(g) == ("buy_dev",)


def test_trades_toward_dev_when_one_point_from_winning():
    """9点で鉱石だけ足りないなら、銀行と交換して買える手札にする。"""
    for seed in range(5):
        g = _at_nine(_main_phase_game(seed), (4, 0, 1, 1, 0))
        a = GreedyAgent(seed=0).act(g)
        assert a == ("trade", 0, 4), a
