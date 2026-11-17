"""MCTS 1人 対 greedy_win 3人を、席を入れ替えて打つ（R-003）。

    python scripts/mcts_match.py --games 100 --workers 4 --sims 48
    python scripts/mcts_match.py --games 100 --workers 4 --sims 48 --out runs/r003

--games は盤（seed）の数。各盤で MCTS が4つの席を1回ずつ打つので、対局数は games × 4。
基準の勝率は 25%。95% の幅の下の端が 25% を超えれば「はっきり強い」。
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from isle.agents import make_agent  # noqa: E402
from isle.arena import play_game  # noqa: E402
from isle.mcts import MCTSAgent  # noqa: E402

MATCH_SEED = 300000  # gate.py（900000〜）や学習と重ならない盤


def one_board(job: tuple) -> list[dict]:
    s, opts, opp = job
    out = []
    for seat in range(4):
        agents = []
        for j in range(4):
            if j == seat:
                agents.append(MCTSAgent(seed=s * 31 + j, **opts))
            else:
                agents.append(make_agent(opp, seed=s * 31 + j))
        t = time.time()
        rec = play_game(agents, s, record=False)
        out.append(
            {
                "seed": s,
                "seat": seat,
                "winner": rec["winner"],
                "win": rec["winner"] == seat,
                "vp": rec["vp"],
                "turns": rec["turns"],
                "searches": agents[seat].searches,
                "seconds": round(time.time() - t, 2),
            }
        )
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=25)
    ap.add_argument("--seed", type=int, default=MATCH_SEED)
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    ap.add_argument("--sims", type=int, default=48)
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument("--c-ucb", type=float, default=0.5)
    ap.add_argument("--temp", type=float, default=1.0)
    ap.add_argument("--opp", default="greedy_win")
    ap.add_argument("--out", default=os.environ.get("RESEARCH_OUT"))
    args = ap.parse_args()
    opts = {"sims": args.sims, "top_k": args.top_k, "c_ucb": args.c_ucb, "temp": args.temp}
    jobs = [(args.seed + i, opts, args.opp) for i in range(args.games)]
    t = time.time()
    recs: list[dict] = []
    with ProcessPoolExecutor(args.workers) as ex:
        for part in ex.map(one_board, jobs):
            recs += part
    n = len(recs)
    wins = sum(r["win"] for r in recs)
    rate = wins / n
    se = math.sqrt(max(rate * (1 - rate), 1e-9) / n)
    res = {
        "opts": opts,
        "opp": args.opp,
        "games": n,
        "wins": wins,
        "win_rate": round(rate, 4),
        "ci95": [round(rate - 1.96 * se, 4), round(rate + 1.96 * se, 4)],
        "avg_vp": round(sum(r["vp"][r["seat"]] for r in recs) / n, 2),
        "seat_wins": [sum(r["win"] for r in recs if r["seat"] == k) for k in range(4)],
        "avg_seconds_per_game": round(sum(r["seconds"] for r in recs) / n, 2),
        "wall_seconds": round(time.time() - t, 1),
    }
    print(json.dumps(res, ensure_ascii=False))
    print(
        f"MCTS の勝率 {rate:.1%}（95%の幅 {res['ci95'][0]:.1%}〜{res['ci95'][1]:.1%}）{n}局 →",
        "25% をはっきり上回る" if res["ci95"][0] > 0.25 else "はっきりしない",
    )
    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "summary.json").write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n")
        with open(out / "games.jsonl", "w", encoding="utf-8") as f:
            for r in recs:
                f.write(json.dumps(r) + "\n")


if __name__ == "__main__":
    main()
