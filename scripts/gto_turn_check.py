"""「この手番で勝てるのに逃した」回数を数える（手番の中の厳密ソルバーとの比較）。

    python scripts/gto_turn_check.py --games 100 --agents greedy

自己対戦の各手番で、サイコロのあと最初に手を選ぶ前にソルバーで勝ち筋を探す。
勝ち筋があるのにAIがその手番で勝たなかったら「見逃し」。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from isle.agents import make_agent  # noqa: E402
from isle.game import MAIN, Game  # noqa: E402
from isle.solver import find_win  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=100)
    ap.add_argument("--agents", default="greedy")
    ap.add_argument("--seed", type=int, default=700000)
    args = ap.parse_args()
    t = time.time()
    stats = {"games": 0, "turns_checked": 0, "win_available": 0, "missed": 0, "examples": []}
    for i in range(args.games):
        s = args.seed + i
        g = Game(seed=s)
        agents = [make_agent(args.agents, seed=s * 10 + j) for j in range(4)]
        checked_turn = -1
        pending = None  # (手番, 人, 勝ち筋)
        while not g.is_over():
            if pending and (g.turns != pending[0]):
                stats["missed"] += 1
                if len(stats["examples"]) < 5:
                    stats["examples"].append({"seed": s, "turn": pending[0], "line": pending[2]})
                pending = None
            if g.phase == MAIN and g.turns != checked_turn:
                checked_turn = g.turns
                stats["turns_checked"] += 1
                line = find_win(g)
                if line:
                    stats["win_available"] += 1
                    pending = (g.turns, g.current, [list(a) for a in line])
            g.apply(agents[g.to_act].act(g))
        if pending and g.winner != pending[1]:
            stats["missed"] += 1
        stats["games"] += 1
    stats["seconds"] = round(time.time() - t)
    print(json.dumps(stats, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
