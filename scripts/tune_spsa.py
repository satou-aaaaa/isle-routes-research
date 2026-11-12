"""評価関数の重みを、対局の勝ち負けから直接合わせる（SPSA）。

毎回、全部の重みを同時に ±delta だけずらした2組（プラス・マイナス）を作り、
4人の席に プラス・マイナス・プラス・マイナス と座らせて席を入れ替えながら打つ。
プラスの勝ちが多ければプラスの向きへ、少なければ逆へ少し動かす。
勝ち負けの相関から学ぶ回帰と違い、「その重みで打つと勝てるか」を直接見る。

    python scripts/tune_spsa.py --iters 60 --games 10 --out models/spsa.json
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from isle.agents import GreedyAgent  # noqa: E402
from isle.arena import run_rotated  # noqa: E402
from isle.features import DEFAULT_WEIGHTS, FEATURES  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--iters", type=int, default=60)
    ap.add_argument("--games", type=int, default=10, help="1回あたりの盤の数（対局は×4）")
    ap.add_argument("--delta", type=float, default=0.15, help="ずらす幅（重みに対する割合）")
    ap.add_argument("--lr", type=float, default=0.6)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--init", help="始めの重み（models/*.json）")
    ap.add_argument("--out", default="models/spsa.json")
    args = ap.parse_args()
    rng = random.Random(args.seed)
    w = list(DEFAULT_WEIGHTS)
    if args.init:
        w = json.loads(Path(args.init).read_text(encoding="utf-8"))["weights"]
    scale = [max(0.05, abs(x)) for x in w]
    t0 = time.time()
    for it in range(args.iters):
        signs = [rng.choice((-1, 1)) for _ in w]
        plus = tuple(x + args.delta * s * c for x, s, c in zip(w, signs, scale, strict=True))
        minus = tuple(x - args.delta * s * c for x, s, c in zip(w, signs, scale, strict=True))

        def make(name, s, plus=plus, minus=minus):
            a = GreedyAgent(plus if name == "plus" else minus, seed=s)
            a.name = name
            return a

        board_seed = args.seed * 100000 + it * 1000
        res = run_rotated(["plus", "minus", "plus", "minus"], make, args.games, seed=board_seed)
        diff = res["agents"]["plus"]["win_rate"] - res["agents"]["minus"]["win_rate"]
        step = args.lr * diff
        w = [x + step * args.delta * s * c for x, s, c in zip(w, signs, scale, strict=True)]
        print(f"{it + 1:3d} plus-minus={diff:+.3f} ({time.time() - t0:.0f}s)", flush=True)
        body = {"features": list(FEATURES), "weights": w, "iters": it + 1, "method": "spsa"}
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(body, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
