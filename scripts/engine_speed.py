"""R-001: 速くしたエンジンと、速くする前の版（tests/ref_game_v0.py）の速さを同じ機械で比べる。

python scripts/engine_speed.py --games 500 --reps 3
"""

from __future__ import annotations

import argparse
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests")]

import ref_game_v0  # noqa: E402

import isle.game as fast  # noqa: E402


def random_games_ms(mod, games: int) -> float:
    t = time.perf_counter()
    for i in range(games):
        g = mod.Game(seed=i)
        rng = random.Random(i)
        while not g.is_over():
            g.apply(rng.choice(g.legal_actions()))
    return (time.perf_counter() - t) / games * 1000


def micro_us(mod, reps: int = 20000) -> tuple[float, float]:
    """中盤の局面1つで、複製と合法手の生成1回あたりの時間（マイクロ秒）。"""
    g = mod.Game(seed=1)
    rng = random.Random(1)
    for _ in range(600):
        g.apply(rng.choice(g.legal_actions()))
    t = time.perf_counter()
    for _ in range(reps):
        g.clone()
    clone = (time.perf_counter() - t) / reps * 1e6
    t = time.perf_counter()
    for _ in range(reps):
        g.legal_actions()
    legal = (time.perf_counter() - t) / reps * 1e6
    return clone, legal


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=500)
    ap.add_argument("--reps", type=int, default=3)
    args = ap.parse_args()
    for _ in range(args.reps):
        old = random_games_ms(ref_game_v0, args.games)
        new = random_games_ms(fast, args.games)
        print(f"ランダム1局: 前の版 {old:.2f}ms → 速い版 {new:.2f}ms（{new / old:.2f}倍）")
    for name, mod in (("前の版", ref_game_v0), ("速い版", fast)):
        c, la = micro_us(mod)
        print(f"{name}: 複製 {c:.1f}µs・合法手の生成 {la:.1f}µs")
    kinds = "・".join(f"{k} {v:.1f}µs" for k, v in clone_kinds_us())
    print(f"速い版の複製の種類（R-006）: {kinds}")


def clone_kinds_us(reps: int = 20000) -> list[tuple[str, float]]:
    """速い版の複製を、乱数の扱い方ごとに比べる（マイクロ秒）。"""
    g = fast.Game(seed=1)
    rng = random.Random(1)
    for _ in range(600):
        g.apply(rng.choice(g.legal_actions()))
    r = random.Random(0)
    kinds = [
        ("乱数を写す clone()", g.clone),
        ("乱数を渡す clone(rng=Random)", lambda: g.clone(rng=r)),
        ("新しい seed clone(rng=int)", lambda: g.clone(rng=12345)),
        ("写さず＋Random を作る", lambda: (g.clone(keep_rng=False), random.Random(1))),
    ]
    out = []
    for name, f in kinds:
        t = time.perf_counter()
        for _ in range(reps):
            f()
        out.append((name, (time.perf_counter() - t) / reps * 1e6))
    return out


if __name__ == "__main__":
    main()
