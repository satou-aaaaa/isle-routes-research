"""AIの打ち手。どれも act(game) で今の手番の人（game.to_act）の手を1つ返す。"""

from __future__ import annotations

import random

from .board import TOPO
from .features import DEFAULT_WEIGHTS, F, evaluate
from .game import (
    COST,
    DISCARD,
    MAIN,
    PRE_ROLL,
    ROBBER,
    STEAL,
    Game,
)
from .solver import find_win

DEV_VP_SHARE = 5 / 25  # 発展カードの山に占める得点カードの割合（買う手の見積もりに使う）
MAX_ACTIONS_PER_TURN = 40  # 交換の行ったり来たりを止める安全弁


class RandomAgent:
    name = "random"

    def __init__(self, seed: int | None = None):
        self.rng = random.Random(seed)

    def act(self, g: Game) -> tuple:
        return self.rng.choice(g.legal_actions())


class GreedyAgent:
    """評価関数で1手先だけを見て、一番よくなる手を選ぶ。

    相手の手札の中身や山札の順番は見ない（発展カードを買う手は平均で見積もる）。
    """

    name = "greedy"

    def __init__(self, weights=DEFAULT_WEIGHTS, seed: int | None = None):
        self.w = weights
        self.rng = random.Random(seed)
        self._turn_key = None
        self._turn_actions = 0

    def value(self, g: Game, p: int) -> float:
        return evaluate(g, p, self.w)

    def act(self, g: Game) -> tuple:
        acts = g.legal_actions()
        if len(acts) == 1:
            return acts[0]
        p = g.to_act
        if g.phase == PRE_ROLL:
            return self._pre_roll(g, p, acts)
        if g.phase == ROBBER:
            return self._robber(g, p, acts)
        if g.phase == STEAL:
            return max(acts, key=lambda a: (g.vp(a[1], hidden=False), g.players[a[1]].cards()))
        if g.phase == DISCARD:
            return self._best(g, p, acts)
        key = (g.turns, g.current)
        if key != self._turn_key:
            self._turn_key, self._turn_actions = key, 0
        self._turn_actions += 1
        if self._turn_actions > MAX_ACTIONS_PER_TURN and ("end",) in acts:
            return ("end",)
        return self._best(g, p, acts)

    # ---- 場面ごと ----
    def _pre_roll(self, g: Game, p: int, acts: list[tuple]) -> tuple:
        if ("knight",) in acts:
            blocked = any(g.building[v] == p for v in TOPO.hex_vertices[g.robber])
            if blocked and g.layout.number[g.robber]:
                return ("knight",)
        return ("roll",)

    def _robber(self, g: Game, p: int, acts: list[tuple]) -> tuple:
        """盗賊は、勝ちに近い相手の産出を一番止められて、自分にはかからない所へ。"""

        def score(a: tuple) -> float:
            h = a[1]
            num = g.layout.number[h]
            if not num:
                return -1.0
            ways = 6 - abs(7 - num)
            s = 0.0
            for v in TOPO.hex_vertices[h]:
                q = g.building[v]
                if q == -1:
                    continue
                k = 2 if g.is_city[v] else 1
                if q == p:
                    s -= 3 * k * ways
                else:
                    s += k * ways * (1 + g.vp(q, hidden=False) / 4)
                    if g.players[q].cards():
                        s += 0.5
            return s + self.rng.random() * 1e-3

        return max(acts, key=score)

    def _best(self, g: Game, p: int, acts: list[tuple]) -> tuple:
        best, best_v = None, -1e18
        for a in acts:
            v = self._action_value(g, p, a)
            if a == ("end",):
                v += 1e-6  # 同じ値なら手番を終える（ムダな交換をしない）
            v += self.rng.random() * 1e-9
            if v > best_v:
                best, best_v = a, v
        return best

    def _action_value(self, g: Game, p: int, a: tuple) -> float:
        c = g.clone()
        if a[0] == "buy_dev":
            # 山札の中身を見ないよう、払うところまで進めて平均で足す
            c._pay(p, COST["dev"])
            return (
                self.value(c, p)
                + self.w[F["dev_hidden"]] * (1 - DEV_VP_SHARE)
                + self.w[F["vp"]] * DEV_VP_SHARE
            )
        c.apply(a)
        v = self.value(c, p)
        if a[0] == "knight" and c.phase == ROBBER:
            v += 0.05  # 盗賊を動かせる分
        return v


class WinCheckAgent(GreedyAgent):
    """貪欲AIに「この手番で勝てる手順があれば必ずそれを打つ」を足したもの（solver.find_win）。"""

    name = "greedy_win"

    def __init__(self, weights=DEFAULT_WEIGHTS, seed: int | None = None):
        super().__init__(weights, seed)
        self._plan: list[tuple] = []
        self._plan_turn = None
        self._checked_turn = None

    def act(self, g: Game) -> tuple:
        if g.to_act == g.current and g.phase not in (PRE_ROLL, DISCARD):
            turn = (g.turns, g.current)
            if self._plan and self._plan_turn == turn:
                a = self._plan[0]
                if a in g.legal_actions():
                    self._plan.pop(0)
                    return a
                self._plan = []
                self._checked_turn = None  # 運で筋が変わったら読み直す
            if g.phase == MAIN and self._checked_turn != turn:
                self._checked_turn = turn
                line = find_win(g)
                if line:
                    self._plan, self._plan_turn = list(line[1:]), turn
                    return line[0]
        return super().act(g)


AGENTS = {"random": RandomAgent, "greedy": GreedyAgent, "greedy_win": WinCheckAgent}


def make_agent(name: str, seed: int | None = None):
    if name not in AGENTS:
        raise ValueError(f"unknown agent {name}; choose from {sorted(AGENTS)}")
    return AGENTS[name](seed=seed)
