"""初期配置クイズ（docs/quiz.html）の問題を作る。

    python scripts/make_quiz.py --puzzles 16 --rollouts 300 --workers 4   # data/quiz.json を書く

1問の作り方:
1. AI（greedy_win）4人で初期配置を進め、決めた順番（1つ目の村・4番手の2つ連続・
   最後の村など）で止める。
2. その人が置ける頂点を、貪欲AIの評価で上から8つ選ぶ。
3. 頂点ごとに、そこへ村を置いてから最後まで AI どうしで打つのを rollouts 回くり返し、
   その人の勝率を出す。サイコロ・山の順番は、どの候補でも k 回目は同じ並びを使う
   （同じ乱数の読み。候補の差が運に埋もれにくい）。
4. 選択肢は、一番の候補と、それより「はっきり」悪い候補（対にした差が標準誤差の2倍以上）から3つ:
   その中で一番よいもの・点（出やすさ）が一番多いもの・一番悪いもの。そろわない局面は捨てる。
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from isle.agents import make_agent  # noqa: E402
from isle.board import GENERIC, dice_ways  # noqa: E402
from isle.game import DEV_DECK, SETUP_SETTLE, Game  # noqa: E402

QUIZ_SEED = 600000  # ほかの測定と重ならない盤
# 何番目の村を問うか（0〜7。0=1番手の1つ目、3=4番手の1つ目、4=4番手の2つ目、7=1番手の2つ目）
STEPS = (0, 3, 4, 7, 1, 6)
AGENT = "greedy_win"


def setup_position(seed: int, step: int) -> Game:
    g = Game(seed=seed)
    agents = [make_agent(AGENT, seed=seed * 10 + j) for j in range(4)]
    while not (g.phase == SETUP_SETTLE and g.setup_step == step):
        g.apply(agents[g.to_act].act(g))
    return g


def vertex_info(g: Game, v: int) -> dict:
    lands = []
    for h, r, num in g.vertex_yield[v]:
        lands.append({"hex": h, "res": r, "num": num, "pips": dice_ways(num)})
    port = g.vertex_port.get(v)
    return {
        "v": v,
        "lands": lands,
        "pips": sum(x["pips"] for x in lands),
        "port": None if port is None else ("3:1" if port == GENERIC else port),
    }


def rollout(g: Game, me: int, v: int, k: int) -> bool:
    c = g.clone(keep_rng=False)
    rng = random.Random(k * 1_000_003 + 17)
    c.rng = random.Random(rng.getrandbits(64))
    deck = list(DEV_DECK)
    rng.shuffle(deck)
    c.dev_deck = deck
    c.apply(("settle", v))
    agents = [make_agent(AGENT, seed=k * 10 + j) for j in range(4)]
    n = 0
    while not c.is_over() and n < 20000:
        c.apply(agents[c.to_act].act(c))
        n += 1
    return c.winner == me


def make_one(job: tuple) -> dict | None:
    seed, step, rollouts, n_cands = job
    g = setup_position(seed, step)
    me = g.current
    greedy = make_agent("greedy", seed=1)
    acts = g.legal_actions()
    scored = sorted(acts, key=lambda a: greedy._action_value(g, me, a), reverse=True)
    cands = [a[1] for a in scored[:n_cands]]
    wins = {v: [rollout(g, me, v, k) for k in range(rollouts)] for v in cands}
    rate = {v: sum(w) / rollouts for v, w in wins.items()}
    order = sorted(cands, key=lambda v: rate[v], reverse=True)
    best = order[0]

    def gap(v: int) -> tuple[float, float]:
        """best − v の勝率の差と、その標準誤差（同じ乱数で打ったので対にして測る）。"""
        diff = [int(a) - int(b) for a, b in zip(wins[best], wins[v], strict=True)]
        mean = sum(diff) / rollouts
        var = sum((d - mean) ** 2 for d in diff) / max(1, rollouts - 1)
        return mean, math.sqrt(var / rollouts)

    # 選択肢に出すのは、一番の候補より「はっきり」悪い候補だけ（差が標準誤差の2倍以上）
    clear = [v for v in order[1:] if gap(v)[1] > 0 and gap(v)[0] >= 2 * gap(v)[1]]
    if len(clear) < 3:
        return None
    info = {v: vertex_info(g, v) for v in cands}
    second = clear[0]
    rest = clear[1:]
    tempting = max(rest, key=lambda v: (info[v]["pips"], rate[v]))
    low = [v for v in reversed(rest) if v != tempting][0]
    mean, se = gap(second)
    choices = [best, second, tempting, low]
    rng = random.Random(seed)
    rng.shuffle(choices)
    return {
        "seed": seed,
        "step": step,
        "me": me,
        "rollouts": rollouts,
        "layout": {
            "terrain": list(g.layout.terrain),
            "number": list(g.layout.number),
            "ports": list(g.layout.ports),
        },
        "building": list(g.building),
        "road": list(g.road),
        "answer": best,
        "choices": [
            {**info[v], "rate": round(rate[v], 4), "greedy_rank": cands.index(v) + 1}
            for v in choices
        ],
        "margin": round(mean, 4),
        "margin_se": round(se, 4),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--puzzles", type=int, default=16, help="作る問題の数（はっきりしない問題は捨てて足す）"
    )
    ap.add_argument("--rollouts", type=int, default=300)
    ap.add_argument("--cands", type=int, default=8)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--seed", type=int, default=QUIZ_SEED)
    ap.add_argument("--out", default=str(ROOT / "data" / "quiz.json"))
    args = ap.parse_args()
    t = time.time()
    out: list[dict] = []
    i = 0
    tried = 0
    with ProcessPoolExecutor(args.workers) as ex:
        while len(out) < args.puzzles and tried < args.puzzles * 4:
            jobs = []
            for _ in range(args.workers):
                jobs.append((args.seed + i, STEPS[i % len(STEPS)], args.rollouts, args.cands))
                i += 1
            for r in ex.map(make_one, jobs):
                tried += 1
                if r and len(out) < args.puzzles:
                    out.append(r)
                    print(
                        f"問題 {len(out)}: seed {r['seed']} "
                        f"差 {r['margin']:.3f}±{r['margin_se']:.3f}",
                        flush=True,
                    )
    out.sort(key=lambda r: (STEPS.index(r["step"]), r["seed"]))
    data = {"agent": AGENT, "rollouts": args.rollouts, "tried": tried, "puzzles": out}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(data, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(out)}問 / {tried}局面（{time.time() - t:.0f}秒）")


if __name__ == "__main__":
    main()
