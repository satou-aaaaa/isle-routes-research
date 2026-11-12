"""新しい重みが今のチャンピオンより強いかを確かめる（1人 対 チャンピオン3人、席を入れ替える）。

    python scripts/gate.py --new runs/spsa.json --games 100
    python scripts/gate.py --new runs/spsa.json --games 100 --promote   # 合格なら採用

基準の勝率は 25%。95% の幅の下の端が 25% を超えたときだけ「強い」とみなす。
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from isle.agents import GreedyAgent  # noqa: E402
from isle.arena import run_rotated  # noqa: E402
from isle.features import FEATURES  # noqa: E402
from isle.models import load, save  # noqa: E402

GATE_SEED = 900000  # 学習に使わない盤


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--new", required=True, help="新しい重みの JSON")
    ap.add_argument("--old", default="champion", help="比べる相手（models/ の名前）")
    ap.add_argument("--games", type=int, default=100)
    ap.add_argument("--promote", action="store_true")
    args = ap.parse_args()
    body = json.loads(Path(args.new).read_text(encoding="utf-8"))
    if body["features"] != list(FEATURES):
        raise SystemExit("特徴量が今のコードと違う")
    new, old = tuple(body["weights"]), load(args.old)

    def make(name, s):
        a = GreedyAgent(new if name == "new" else old, seed=s)
        a.name = name
        return a

    t = time.time()
    res = run_rotated(["new", "old", "old", "old"], make, args.games, seed=GATE_SEED)
    r = res["agents"]["new"]
    print(
        f"新しい重みの勝率 {r['win_rate']:.1%}（95%の幅 {r['ci95'][0]:.1%}〜{r['ci95'][1]:.1%}）"
        f" {res['games']}局 {time.time() - t:.0f}秒"
    )
    passed = r["ci95"][0] > 0.25
    print("合格" if passed else "不合格")
    if passed and args.promote:
        meta = {
            "date": dt.date.today().isoformat(),
            "source": body.get("method", Path(args.new).name),
            "gate": {"games": res["games"], "win_rate": r["win_rate"], "vs": args.old},
        }
        print("採用:", save(new, "champion", meta))


if __name__ == "__main__":
    main()
