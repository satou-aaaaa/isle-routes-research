"""PRを出す前・マージする前の確認を1コマンドで行う（CIも同じものを実行する）。

python scripts/check.py           # lint・整形・全テスト
python scripts/check.py --quick   # 時間のかかる強さの検証（@pytest.mark.slow）を飛ばす
python scripts/check.py --fix     # 先に ruff の自動修正と整形をかけてから確認する
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable


def step(name: str, cmd: list[str]) -> None:
    t = time.time()
    print(f"== {name}: {' '.join(cmd)}", flush=True)
    r = subprocess.run(cmd, cwd=ROOT, check=False)
    if r.returncode:
        raise SystemExit(f"✗ {name} が失敗しました")
    print(f"✓ {name}（{time.time() - t:.0f}秒）", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="slow マーク付きのテストを飛ばす")
    ap.add_argument("--fix", action="store_true", help="ruff の自動修正と整形を先にかける")
    args = ap.parse_args()
    if args.fix:
        step("ruff 自動修正", [PY, "-m", "ruff", "check", "--fix", "."])
        step("ruff 整形", [PY, "-m", "ruff", "format", "."])
    step("ruff", [PY, "-m", "ruff", "check", "."])
    step("ruff 整形の確認", [PY, "-m", "ruff", "format", "--check", "."])
    test = [PY, "-m", "pytest", "-q"] + (["-m", "not slow"] if args.quick else [])
    step("pytest" + ("（slow を除く）" if args.quick else ""), test)
    print("すべて通りました")


if __name__ == "__main__":
    main()
