"""初期配置クイズ（docs/quiz.html）のデータと解説を、data/quiz.json から組み立てる。

問題づくり: python scripts/make_quiz.py --puzzles 12 --rollouts 200 --cands 6 --workers 4
ここでは、盤の形（src/isle/board.py）と問題を docs/quiz_data.js に書き、
各問の「学び」の1文を、正解と選択肢の違い（点・資源の種類・鉱石と小麦・港）から日英で作る。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from isle.board import PORT_EDGES, TOPO, dice_ways  # noqa: E402

QUIZ = ROOT / "data" / "quiz.json"
RES = {
    "ja": ("木材", "れんが", "羊毛", "小麦", "鉱石"),
    "en": ("wood", "brick", "wool", "grain", "ore"),
}
ORE, GRAIN = 4, 3


def _hex_vertices_yield(layout: dict) -> list[list[tuple[int, int]]]:
    """頂点ごとの (資源, 点)。"""
    out: list[list[tuple[int, int]]] = [[] for _ in TOPO.vertex_xy]
    for h, vs in enumerate(TOPO.hex_vertices):
        t, n = layout["terrain"][h], layout["number"][h]
        if t < 0:
            continue
        for v in vs:
            out[v].append((t, dice_ways(n)))
    return out


def _kinds(yields: list[tuple[int, int]]) -> set[int]:
    return {r for r, _ in yields}


def lesson(p: dict) -> dict[str, str]:
    """正解が選ばれた理由の目安を1文で（日英）。"""
    y = _hex_vertices_yield(p["layout"])
    own = [v for v, q in enumerate(p["building"]) if q == p["me"]]
    have = set().union(*[_kinds(y[v]) for v in own]) if own else set()
    by_v = {c["v"]: c for c in p["choices"]}
    best = by_v[p["answer"]]
    others = [c for c in p["choices"] if c["v"] != p["answer"]]
    rich = max(others, key=lambda c: c["pips"])

    def kinds_after(c: dict) -> int:
        return len(have | _kinds(y[c["v"]]))

    def og(c: dict) -> int:
        return sum(pp for r, pp in y[c["v"]] if r in (ORE, GRAIN))

    if rich["pips"] > best["pips"] and kinds_after(best) > kinds_after(rich):
        return {
            "ja": f"点の合計は{rich['pips']}点の候補の方が多いのに、正解は{best['pips']}点。"
            f"自分の資源が{kinds_after(best)}種類にそろう方が勝ちやすかった。",
            "en": f"Another spot had more dots ({rich['pips']} vs {best['pips']}), but the answer "
            f"brings you to {kinds_after(best)} resource types, and that won more often.",
        }
    if og(best) > max(og(c) for c in others):
        return {
            "ja": "選択肢の中で小麦と鉱石が一番出やすい場所。街と発展カードに要る資源が"
            "勝ちやすさにつながった。",
            "en": "Of the choices, this spot produces the most grain and ore, the resources for "
            "towns and development cards, and that won more often.",
        }
    if rich["pips"] > best["pips"]:
        return {
            "ja": f"点の合計だけなら{rich['pips']}点の候補が上。数字の並び・まわりの相手・"
            "その後の置き場所まで含めると、正解の方が勝ちやすかった。",
            "en": f"By dots alone the {rich['pips']}-dot spot is better. Counting the numbers, "
            "the neighbors and future spots, the answer still won more often.",
        }
    if kinds_after(best) > max(kinds_after(c) for c in others):
        return {
            "ja": f"点が多いうえに、自分の資源が{kinds_after(best)}種類にそろう。",
            "en": f"More dots, and your resources cover {kinds_after(best)} types.",
        }
    hot = any(n in (6, 8) for n in _numbers(p, best["v"]))
    k = kinds_after(best)
    return {
        "ja": f"正解は点の合計{best['pips']}点で、選択肢の中で一番多い場所。"
        + ("よく出る6か8に接していて、" if hot else "")
        + f"自分の資源が{k}種類になる。まずは出やすさの合計で比べるのが基本。",
        "en": f"The answer has {best['pips']} dots, the most among the choices"
        + (", touches a 6 or 8," if hot else "")
        + f" and gives you {k} resource types. Comparing total dots is the place to start.",
    }


def _numbers(p: dict, v: int) -> list[int]:
    return [p["layout"]["number"][h] for h, vs in enumerate(TOPO.hex_vertices) if v in vs]


def data_js() -> str:
    q = json.loads(QUIZ.read_text(encoding="utf-8"))
    puzzles = []
    for p in q["puzzles"]:
        puzzles.append({**p, "lesson": lesson(p)})
    geo = {
        "hexes": [list(xy) for xy in TOPO.hex_xy],
        "vertices": [list(xy) for xy in TOPO.vertex_xy],
        "edges": [list(e) for e in TOPO.edges],
        "port_edges": list(PORT_EDGES),
    }
    data = {"geo": geo, "rollouts": q["rollouts"], "agent": q["agent"], "puzzles": puzzles}
    return (
        "// scripts/build_quiz.py が data/quiz.json から作る（手で直さない）\n"
        "window.QUIZ = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n"
    )


def count() -> int:
    return len(json.loads(QUIZ.read_text(encoding="utf-8"))["puzzles"])
