"""終盤1巡の読み切りで、AI の手が最善からどれだけ外れるかを測る（R-002）。

    python scripts/round_check.py --games 40 --workers 4 --out runs/round_check

greedy_win どうしの自己対戦で、誰かが8点以上のときの「サイコロのあと最初の手」の局面を集め、
各局面で根（手番の人）について次を求める（相手の考え方 max^n と paranoid の2通り）。

- best: 読み切りの最善を打ったときの「この1巡で根が勝つ確率」
- greedy / greedy_win: 根がそのAIの手を打ったときの同じ確率

外れ（best − AI）が大きい局面ほど、AIがこの1巡の勝ち筋か守りを逃している。
読む局面が上限を超えた局面は外して数える（too_big）。
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from isle.agents import make_agent  # noqa: E402
from isle.game import MAIN, Game  # noqa: E402
from isle.round_solver import MAXN, PARANOID, RoundSolver, TooBig, agent_chooser  # noqa: E402

AGENT_NAMES = ("greedy", "greedy_win")


def positions(seed: int, min_vp: int):
    g = Game(seed=seed)
    agents = [make_agent("greedy_win", seed=seed * 10 + j) for j in range(4)]
    last = -1
    while not g.is_over():
        if g.phase == MAIN and g.turns != last:
            last = g.turns
            if max(g.vp(q) for q in range(4)) >= min_vp:
                yield g.clone()
        g.apply(agents[g.to_act].act(g))


def solve_game(args: tuple) -> list[dict]:
    seed, min_vp, max_nodes, max_ends = args
    out = []
    for g in positions(seed, min_vp):
        rec = {
            "seed": seed,
            "turn": g.turns,
            "root": g.current,
            "vp": [g.vp(q) for q in range(4)],
            "hand": list(g.players[g.current].hand),
        }
        t = time.time()
        try:
            for mode in (MAXN, PARANOID):
                rs = RoundSolver(g.current, mode, max_nodes=max_nodes, max_ends=max_ends)
                r = {"best": rs.value(g.clone())}
                for name in AGENT_NAMES:
                    r[name] = rs.agent_value(g.clone(), agent_chooser(make_agent(name, seed=1)))
                r["ends"] = len(rs._end_memo)
                rec[mode] = r
        except TooBig as e:
            rec["too_big"] = str(e)
        rec["sec"] = round(time.time() - t, 2)
        out.append(rec)
    return out


def summarize(recs: list[dict]) -> dict:
    ok = [r for r in recs if "too_big" not in r]
    s: dict = {
        "positions": len(recs),
        "solved": len(ok),
        "too_big": len(recs) - len(ok),
        "games": len({r["seed"] for r in recs}),
        "sec_median": statistics.median([r["sec"] for r in recs]) if recs else 0,
    }
    for mode in (MAXN, PARANOID):
        m: dict = {
            "best_mean": round(statistics.fmean(r[mode]["best"] for r in ok), 4) if ok else 0
        }
        for name in AGENT_NAMES:
            gaps = [r[mode]["best"] - r[mode][name] for r in ok]
            m[name] = {
                "value_mean": round(statistics.fmean(r[mode][name] for r in ok), 4) if ok else 0,
                "gap_mean": round(statistics.fmean(gaps), 4) if gaps else 0,
                "gap_max": round(max(gaps), 4) if gaps else 0,
                "gap_over_1pct": sum(1 for x in gaps if x > 0.01),
                "gap_over_5pct": sum(1 for x in gaps if x > 0.05),
            }
        s[mode] = m
    return s


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=40)
    ap.add_argument("--seed", type=int, default=800000)
    ap.add_argument("--min-vp", type=int, default=8)
    ap.add_argument("--max-nodes", type=int, default=4000)
    ap.add_argument("--max-ends", type=int, default=600)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    t = time.time()
    jobs = [(args.seed + i, args.min_vp, args.max_nodes, args.max_ends) for i in range(args.games)]
    recs: list[dict] = []
    out_dir = Path(args.out) if args.out else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for i, res in enumerate(ex.map(solve_game, jobs)):
            recs.extend(res)
            print(
                f"game {i + 1}/{args.games} positions={len(recs)} {time.time() - t:.0f}s",
                flush=True,
            )
            if out_dir:
                with open(out_dir / "positions.jsonl", "a") as f:
                    for r in res:
                        f.write(json.dumps(r) + "\n")
    s = summarize(recs)
    s["seconds"] = round(time.time() - t)
    print(json.dumps(s, ensure_ascii=False, indent=1))
    if out_dir:
        (out_dir / "summary.json").write_text(json.dumps(s, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
