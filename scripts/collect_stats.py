"""AI どうしの対局から、データページ（docs/stats.html）の数字を集める。

    python scripts/collect_stats.py --games 4000 --workers 4            # data/stats.json を書く
    python scripts/collect_stats.py --games 4000 --workers 4 --rows runs/stats_rows.jsonl

1人1行の記録（席・初期配置・終局の点の内訳・勝ち負け）を集め、集計を data/stats.json に書く。
ページの本文の数字は、この集計から組み立てる（手で書かない）。
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from isle.agents import make_agent  # noqa: E402
from isle.board import GENERIC, dice_ways  # noqa: E402
from isle.game import MAIN, VP_CARD, Game  # noqa: E402

STATS_SEED = 700000  # gate・研究の対局と重ならない盤
AGENT = "greedy_win"


def _vertex_info(g: Game, v: int) -> dict:
    pips = [0] * 5
    for _h, r, num in g.vertex_yield[v]:
        pips[r] += dice_ways(num)
    return {"pips": pips, "port": g.vertex_port.get(v)}


def play_one(seed: int) -> list[dict]:
    g = Game(seed=seed)
    agents = [make_agent(AGENT, seed=seed * 10 + j) for j in range(4)]
    starts: list[list[int]] = [[] for _ in range(4)]
    sevens = 0
    rolls = 0
    bought = [0] * 4
    first_main_vp_leader_turn = {}
    while not g.is_over():
        q = g.to_act
        a = agents[q].act(g)
        if a[0] == "settle":
            starts[g.current].append(a[1])
        if a[0] == "buy_dev":
            bought[g.current] += 1
        g.apply(a)
        if a[0] == "roll":
            rolls += 1
            sevens += g.last_roll == 7
        if g.phase == MAIN and g.turns % 4 == 0 and g.turns not in first_main_vp_leader_turn:
            first_main_vp_leader_turn[g.turns] = [g.vp(p, hidden=False) for p in range(4)]
    rows = []
    # 折り返し（全手番の半分）の時点で見えている点が一番多かった人
    half = (g.turns // 2) // 4 * 4
    mid = first_main_vp_leader_turn.get(half)
    for p in range(4):
        pl = g.players[p]
        info = [_vertex_info(g, v) for v in starts[p]]
        pips = [sum(i["pips"][r] for i in info) for r in range(5)]
        ports = [i["port"] for i in info if i["port"] is not None]
        rows.append(
            {
                "seed": seed,
                "seat": p,
                "win": g.winner == p,
                "turns": g.turns,
                "vp": g.vp(p),
                "settlements": pl.settlements,
                "cities": pl.cities,
                "longest": g.longest_holder == p,
                "army": g.army_holder == p,
                "vp_cards": pl.dev[VP_CARD],
                "knights": pl.knights,
                "bought": bought[p],
                "start_pips": pips,
                "start_kinds": sum(1 for x in pips if x),
                "start_port": (
                    "none" if not ports else ("generic" if GENERIC in ports else "special")
                ),
                "mid_vp": mid[p] if mid else None,
                "mid_lead": bool(mid) and mid[p] == max(mid) and mid.count(max(mid)) == 1,
                "sevens": sevens,
                "rolls": rolls,
            }
        )
    return rows


def _rate(xs: list[bool]) -> dict:
    n = len(xs)
    k = sum(xs)
    p = k / n if n else 0.0
    se = math.sqrt(max(p * (1 - p), 1e-9) / max(n, 1))
    return {
        "n": n,
        "rate": round(p, 4),
        "lo": round(max(0, p - 1.96 * se), 4),
        "hi": round(min(1, p + 1.96 * se), 4),
    }


def summarize(rows: list[dict]) -> dict:
    games = len({r["seed"] for r in rows})
    winners = [r for r in rows if r["win"]]
    out: dict = {"games": games, "agent": AGENT}
    out["seat"] = [_rate([r["win"] for r in rows if r["seat"] == s]) for s in range(4)]
    out["turns_mean"] = round(statistics.fmean(r["turns"] for r in rows if r["seat"] == 0) / 4, 1)
    out["no_winner"] = games - len(winners)
    # 勝った人の10点の内訳
    parts = {"settlements": 0.0, "cities": 0.0, "longest": 0.0, "army": 0.0, "vp_cards": 0.0}
    for r in winners:
        parts["settlements"] += r["settlements"]
        parts["cities"] += 2 * r["cities"]
        parts["longest"] += 2 * r["longest"]
        parts["army"] += 2 * r["army"]
        parts["vp_cards"] += r["vp_cards"]
    nw = max(1, len(winners))
    out["winner_points"] = {k: round(v / nw, 2) for k, v in parts.items()}
    out["winner_vp"] = round(statistics.fmean(r["vp"] for r in winners), 2) if winners else 0
    out["loser_vp"] = round(statistics.fmean(r["vp"] for r in rows if not r["win"]), 2)
    out["bonus_win"] = {
        "longest": _rate([r["win"] for r in rows if r["longest"]]),
        "army": _rate([r["win"] for r in rows if r["army"]]),
        "neither": _rate([r["win"] for r in rows if not r["longest"] and not r["army"]]),
    }
    # 初期配置の出やすさ（2つの村の点の合計）ごとの勝率
    bins = [(0, 15), (16, 18), (19, 21), (22, 24), (25, 99)]
    out["start_pips"] = []
    for lo, hi in bins:
        sub = [r["win"] for r in rows if lo <= sum(r["start_pips"]) <= hi]
        if sub:
            out["start_pips"].append({"min": lo, "max": hi, **_rate(sub)})
    out["start_pips_mean"] = round(statistics.fmean(sum(r["start_pips"]) for r in rows), 1)
    out["start_kinds"] = [
        {"kinds": k, **_rate([r["win"] for r in rows if r["start_kinds"] == k])}
        for k in range(2, 6)
        if any(r["start_kinds"] == k for r in rows)
    ]
    out["start_port"] = {
        k: _rate([r["win"] for r in rows if r["start_port"] == k])
        for k in ("none", "generic", "special")
    }
    # 資源ごと: 初期配置でその資源の出やすさが「多い（4点以上）」人の勝率
    names = ("wood", "brick", "wool", "grain", "ore")
    out["start_resource"] = {}
    for i, name in enumerate(names):
        rich = [r["win"] for r in rows if r["start_pips"][i] >= 5]
        none = [r["win"] for r in rows if r["start_pips"][i] == 0]
        out["start_resource"][name] = {"rich": _rate(rich), "none": _rate(none)}
    # 折り返しでリードしていた人の勝率
    led = [r["win"] for r in rows if r["mid_lead"]]
    out["mid_lead"] = _rate(led)
    out["dev_bought"] = {
        "winner_mean": round(statistics.fmean(r["bought"] for r in winners), 2) if winners else 0,
        "loser_mean": round(statistics.fmean(r["bought"] for r in rows if not r["win"]), 2),
    }
    sev = [r for r in rows if r["seat"] == 0]
    out["seven_share"] = round(
        sum(r["sevens"] for r in sev) / max(1, sum(r["rolls"] for r in sev)), 4
    )
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=4000)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--seed", type=int, default=STATS_SEED)
    ap.add_argument("--rows", default="", help="1人1行の記録の書き出し先（JSONL）")
    ap.add_argument("--out", default=str(ROOT / "data" / "stats.json"))
    ap.add_argument("--from-rows", default="", help="対局せず、前に書き出した記録から集計し直す")
    args = ap.parse_args()
    t = time.time()
    if args.from_rows:
        rows = [json.loads(x) for x in open(args.from_rows, encoding="utf-8")]
        s = summarize(rows)
        Path(args.out).write_text(json.dumps(s, ensure_ascii=False, indent=1) + "\n", "utf-8")
        return
    seeds = range(args.seed, args.seed + args.games)
    with ProcessPoolExecutor(args.workers) as ex:
        rows = [r for rs in ex.map(play_one, seeds, chunksize=8) for r in rs]
    if args.rows:
        Path(args.rows).parent.mkdir(parents=True, exist_ok=True)
        with open(args.rows, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
    s = summarize(rows)
    s["seconds"] = round(time.time() - t, 1)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(s, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(s, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
