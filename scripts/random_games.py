"""ランダムに打つ4人の対局を回し、終わるまでの手数・速さ・席ごとの勝ち数を出す（エンジンの点検用）。

python scripts/random_games.py --games 1000
"""

from __future__ import annotations

import argparse
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from isle.game import Game  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=200)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    wins = [0] * 4
    turns = 0
    t = time.time()
    for i in range(args.games):
        g = Game(seed=args.seed + i)
        rng = random.Random(args.seed + i)
        while not g.is_over():
            g.apply(rng.choice(g.legal_actions()))
        if g.winner is not None:
            wins[g.winner] += 1
        turns += g.turns
    dt = time.time() - t
    print(f"{args.games}局 {dt:.1f}秒（1局 {dt / args.games * 1000:.0f}ms）")
    print(f"平均 {turns / args.games:.0f} 手番、席ごとの勝ち数 {wins}")


if __name__ == "__main__":
    main()
