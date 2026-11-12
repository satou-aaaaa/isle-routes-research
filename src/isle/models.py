"""評価関数の重みの保存と読み込み（models/<名前>.json）。"""

from __future__ import annotations

import json
from pathlib import Path

from .features import DEFAULT_WEIGHTS, FEATURES

MODEL_DIR = Path(__file__).resolve().parents[2] / "models"


def load(name: str = "champion"):
    """重みを読む。ファイルが無ければ手で決めた重みを返す。"""
    path = MODEL_DIR / f"{name}.json"
    if not path.exists():
        return DEFAULT_WEIGHTS
    body = json.loads(path.read_text(encoding="utf-8"))
    if body["features"] != list(FEATURES):
        raise ValueError(f"{path} の特徴量が今のコードと違う")
    return tuple(body["weights"])


def save(weights, name: str, meta: dict) -> Path:
    MODEL_DIR.mkdir(exist_ok=True)
    path = MODEL_DIR / f"{name}.json"
    body = {"features": list(FEATURES), "weights": [float(x) for x in weights], **meta}
    path.write_text(json.dumps(body, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return path
