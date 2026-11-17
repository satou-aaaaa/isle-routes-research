"""決定化した MCTS（src/isle/mcts.py）のテスト。"""

from __future__ import annotations

import random

from isle.agents import make_agent
from isle.arena import play_game
from isle.game import DEV_DECK, MAIN, Game
from isle.mcts import MCTSAgent, determinize


def _midgame(seed: int, steps: int = 400) -> Game:
    g = Game(seed=seed)
    agents = [make_agent("greedy", seed=seed * 4 + j) for j in range(4)]
    for _ in range(steps):
        if g.is_over():
            break
        g.apply(agents[g.to_act].act(g))
    return g


def _dev_total(g: Game) -> list[int]:
    out = [0] * 5
    for c in g.dev_deck:
        out[c] += 1
    for pl in g.players:
        for c in range(5):
            out[c] += pl.dev[c]
    return out


def test_determinize_keeps_what_me_sees():
    g = _midgame(7)
    me = g.to_act
    before = (g.dev_deck[:], [pl.dev[:] for pl in g.players], g.rng.getstate())
    for k in range(20):
        c = determinize(g, me, random.Random(k))
        # 自分の札・全員の札の枚数・手札・盤は同じ
        assert c.players[me].dev == g.players[me].dev
        for q in range(4):
            assert sum(c.players[q].dev) == sum(g.players[q].dev)
            assert sum(c.players[q].dev_new) == sum(g.players[q].dev_new)
            assert c.players[q].hand == g.players[q].hand
        assert len(c.dev_deck) == len(g.dev_deck)
        assert c.building == g.building and c.road == g.road
        # 山と手元の札の種類ごとの数は変わらない（配り直しただけ）
        total = _dev_total(c)
        assert all(total[i] <= DEV_DECK.count(i) for i in range(5))
        assert total == _dev_total(g)
    # もとの局面（乱数も）は変わらない
    assert before == (g.dev_deck, [pl.dev for pl in g.players], g.rng.getstate())


def test_determinize_reshuffles_hidden_cards():
    g = _midgame(3)
    decks = {tuple(determinize(g, g.to_act, random.Random(k)).dev_deck) for k in range(10)}
    assert len(decks) > 1


def test_mcts_plays_a_legal_game():
    agents = [MCTSAgent(seed=1, sims=8)] + [make_agent("greedy_win", seed=j) for j in range(3)]
    rec = play_game(agents, seed=12, record=False)
    assert rec["winner"] is not None
    assert agents[0].searches > 0


def test_mcts_returns_a_legal_action_in_main():
    checked = 0
    for seed in range(30):
        g = _midgame(seed, steps=200 + seed * 13)
        while not g.is_over() and not (g.phase == MAIN and len(g.legal_actions()) > 2):
            g.apply(make_agent("greedy", seed=seed).act(g))
        if g.is_over():
            continue
        a = MCTSAgent(seed=0, sims=6).act(g)
        assert a in g.legal_actions()
        checked += 1
        if checked >= 5:
            break
    assert checked >= 3
