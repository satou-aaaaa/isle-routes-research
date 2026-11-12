"""対局を回し、記録（JSONL）と成績をまとめる。

記録は seed と手の列だけを持つ。同じ seed の Game に同じ手を順に apply すれば、
サイコロ・盗むカード・山札も含めて同じ対局が再現できる（replay）。
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Sequence

from .game import Game

MAX_ACTIONS = 20000  # 1局の手の数の上限（安全弁）


def play_game(agents: Sequence, seed: int, record: bool = True) -> dict:
    g = Game(n_players=len(agents), seed=seed)
    actions: list[list] = []
    n = 0
    while not g.is_over() and n < MAX_ACTIONS:
        a = agents[g.to_act].act(g)
        g.apply(a)
        if record:
            actions.append(list(a))
        n += 1
    return {
        "seed": seed,
        "agents": [getattr(a, "name", type(a).__name__) for a in agents],
        "winner": g.winner,
        "vp": [g.vp(q) for q in range(g.n)],
        "turns": g.turns,
        "actions": actions if record else None,
    }


def replay(rec: dict) -> Game:
    g = Game(n_players=len(rec["agents"]), seed=rec["seed"])
    for a in rec["actions"]:
        g.apply(tuple(a))
    return g


def run_rotated(
    names: Sequence[str],
    make: Callable[[str, int], object],
    games: int,
    seed: int = 0,
    log_path: str | None = None,
    record: bool = False,
) -> dict:
    """席を順にずらして打つ（同じ seed で全員が全部の席を1回ずつ）。

    games は seed の数。対局数は games × 人数になる。
    """
    n = len(names)
    labels = list(names)
    wins = {name: 0.0 for name in set(labels)}
    plays = {name: 0 for name in set(labels)}
    vp_sum = {name: 0.0 for name in set(labels)}
    seat_wins = [0] * n
    turns = 0
    total = 0
    log = open(log_path, "a", encoding="utf-8") if log_path else None
    try:
        for i in range(games):
            s = seed + i
            for k in range(n):
                seat_names = [labels[(j + k) % n] for j in range(n)]
                agents = [make(name, s * 31 + j) for j, name in enumerate(seat_names)]
                rec = play_game(agents, s, record=record or bool(log))
                total += 1
                turns += rec["turns"]
                for j, name in enumerate(seat_names):
                    plays[name] += 1
                    vp_sum[name] += rec["vp"][j]
                w = rec["winner"]
                if w is not None:
                    seat_wins[w] += 1
                    # 同じ名前が複数の席にいるときは、その名前の勝ちとして数える
                    wins[seat_names[w]] += 1
                if log:
                    log.write(json.dumps(rec, ensure_ascii=False) + "\n")
    finally:
        if log:
            log.close()
    out = {"games": total, "avg_turns": turns / max(1, total), "seat_wins": seat_wins, "agents": {}}
    for name in sorted(wins):
        # 1人あたりの勝率（同じ名前が m 席いれば m で割る）
        m = labels.count(name)
        rate = wins[name] / total / m
        se = math.sqrt(max(rate * (1 - rate), 1e-9) / (total * m))
        out["agents"][name] = {
            "seats": m,
            "win_rate": rate,
            "ci95": [max(0.0, rate - 1.96 * se), min(1.0, rate + 1.96 * se)],
            "avg_vp": vp_sum[name] / plays[name],
        }
    return out
