"""4人の対局を席を入れ替えながら回し、勝率を出す。

    python scripts/run_match.py --agents greedy,random,random,random --games 50
    python scripts/run_match.py --agents greedy,random,random,random --games 50 --log runs/m.jsonl

--games は盤（seed）の数。各盤で全員が全部の席を1回ずつ打つので、対局数は games × 4。
基準の勝率は 1/4 = 25%。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from isle.agents import make_agent  # noqa: E402
from isle.arena import run_rotated  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--agents", default="greedy,random,random,random")
    ap.add_argument("--games", type=int, default=20)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--log", help="対局の記録を JSONL で足していく")
    args = ap.parse_args()
    names = args.agents.split(",")
    if args.log:
        Path(args.log).parent.mkdir(parents=True, exist_ok=True)
    t = time.time()
    res = run_rotated(names, make_agent, args.games, seed=args.seed, log_path=args.log)
    res["seconds"] = round(time.time() - t, 1)
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
