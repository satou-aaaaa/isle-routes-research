"""データページ（docs/stats.html）の数字と言い切りを、data/stats.json から組み立てる。

本文の {{名前}} を、集計から作った値（日英それぞれ）で置き換える。
「学び」の言い切りは集計が支えるときだけ出し、支えないときは止める（check_claims）。
集計し直し: python scripts/collect_stats.py --games 10000 --workers 4
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATS = ROOT / "data" / "stats.json"

RES = {
    "ja": ("木材", "れんが", "羊毛", "小麦", "鉱石"),
    "en": ("Wood", "Brick", "Wool", "Grain", "Ore"),
}
RES_KEYS = ("wood", "brick", "wool", "grain", "ore")
SEATS = {"ja": ("1番手", "2番手", "3番手", "4番手"), "en": ("1st", "2nd", "3rd", "4th")}
PARTS = {
    "ja": {
        "settlements": "村",
        "cities": "街",
        "longest": "最長の道",
        "army": "最大の騎士",
        "vp_cards": "得点カード",
    },
    "en": {
        "settlements": "Villages",
        "cities": "Towns",
        "longest": "Longest road",
        "army": "Largest army",
        "vp_cards": "Point cards",
    },
}


def pct(x: float, digits: int = 1) -> str:
    return f"{x * 100:.{digits}f}%"


def ci(r: dict) -> str:
    return f"{pct(r['lo'])}–{pct(r['hi'])}"


def bars(rows: list[tuple[str, float, str]], scale: float, ref: float | None = None) -> str:
    """横棒グラフ。rows は (ラベル, 値, 右に出す文字)。scale は棒の長さ100%に当たる値。"""
    out = ['<div class="bars">']
    for label, v, text in rows:
        w = max(0.0, min(100.0, v / scale * 100))
        out.append(
            f'<div class="bar-row"><span class="bar-name">{label}</span>'
            f'<span class="bar"><span class="fill" style="width:{w:.1f}%"></span>'
            + (
                f'<span class="ref" style="left:{ref / scale * 100:.1f}%"></span>'
                if ref is not None
                else ""
            )
            + f'</span><span class="bar-val">{text}</span></div>'
        )
    out.append("</div>")
    return "".join(out)


def check_claims(s: dict) -> None:
    """本文に書いた言い切りが、集計で支えられているか確かめる。外れたら止める。"""
    pts = s["winner_points"]
    if max(pts, key=pts.get) != "cities":
        raise SystemExit(
            "stats: 「街が一番大きな点のもと」が集計と合いません（web/stats_body.html を直す）"
        )
    if not s["mid_lead"]["lo"] > 0.25 or not s["mid_lead"]["hi"] < 0.5:
        raise SystemExit("stats: 「4人に1人より高いが半分も逃げ切れない」が集計と合いません")


def values(s: dict, lang: str) -> dict[str, str]:
    ja = lang == "ja"
    seat = s["seat"]
    first, last = seat[0], seat[3]
    if first["lo"] > 0.25 and first["lo"] > last["hi"]:
        seat_text = (
            f"1番手が{pct(first['rate'])}（{ci(first)}）で一番勝ち、4番手は{pct(last['rate'])}でした。"
            if ja
            else f"The 1st seat won {pct(first['rate'])} ({ci(first)}), the most, and the 4th seat "
            f"{pct(last['rate'])}."
        )
        seat_lesson = (
            "1番手は最初の村を一番よい場所に置けて、手番も一番早く回ってきます。"
            "4番手は2つの村を続けて置けるので、2つの組み合わせ（種類のそろい・港）で取り返しましょう。"
            if ja
            else "The 1st seat gets the best first spot and the earliest turns. "
            "The 4th seat places two villages in a row, so make up for it with a good "
            "combination (all resource types, a matching harbor)."
        )
    else:
        seat_text = (
            "席による勝率の差ははっきりしませんでした。"
            if ja
            else "The seat made no clear difference."
        )
        seat_lesson = (
            "何番手でも勝ちやすさはほぼ同じです。"
            if ja
            else "Your seat barely changes your chances."
        )
    seat_bars = bars(
        [(SEATS[lang][i], r["rate"], pct(r["rate"])) for i, r in enumerate(seat)], 0.4, ref=0.25
    )
    pts = s["winner_points"]
    unit = "点" if ja else " pts"
    points_bars = bars([(PARTS[lang][k], v, f"{v:.2f}{unit}") for k, v in pts.items()], 5.0)
    bw = s["bonus_win"]
    nb = bw["neither"]["rate"]
    if nb < 0.1:
        bonus_lesson = (
            f"最長の道か最大の騎士のどちらかがないと、勝つのはとても難しい（{pct(nb)}）。"
            "道を延ばすか騎士を集めるか、どちらで2点を取るかを早めに決めましょう。"
            if ja
            else f"Without the longest road or the largest army, winning is very hard ({pct(nb)}). "
            "Decide early whether you will take those 2 points by extending roads or by "
            "collecting knights."
        )
    else:
        bonus_lesson = (
            "最長の道や最大の騎士がなくても勝てることがあります。"
            if ja
            else "You can win without the longest road or the largest army."
        )
    # 「勝った人が最長の道か最大の騎士を持っていた割合」は、どちらも持たない勝者の数から出す
    winners_neither = bw["neither"]["rate"] * bw["neither"]["n"] / s["games"]
    pips_rows = []
    for b in s["start_pips"]:
        if b["n"] < 300:
            continue
        label = f"{b['min']}–{b['max']}" if b["max"] < 99 else f"{b['min']}+"
        if b["min"] == 0:
            label = f"≤{b['max']}"
        pips_rows.append((label, b["rate"], pct(b["rate"])))
    kinds = {k["kinds"]: k for k in s["start_kinds"]}
    sr = s["start_resource"]
    head = ("資源", "多い", "なし") if ja else ("Resource", "Plenty", "None")
    trs = "".join(
        f"<tr><td>{RES[lang][i]}</td><td>{pct(sr[k]['rich']['rate'])}</td>"
        f"<td>{pct(sr[k]['none']['rate'])}</td></tr>"
        for i, k in enumerate(RES_KEYS)
    )
    res_table = (
        f'<div class="scroll"><table class="res"><tr><th>{head[0]}</th><th>{head[1]}</th>'
        f"<th>{head[2]}</th></tr>{trs}</table></div>"
    )
    gaps = {k: sr[k]["rich"]["rate"] - sr[k]["none"]["rate"] for k in RES_KEYS}
    top = sorted(gaps, key=gaps.get, reverse=True)[:2]
    ore_gap = sr["ore"]["rich"]["rate"] - sr["ore"]["none"]["rate"]
    names = [RES[lang][RES_KEYS.index(k)] for k in top]
    if kinds.get(5) and kinds.get(4) and kinds[5]["lo"] > kinds[4]["hi"]:
        start_lesson = (
            f"点の合計を増やすだけでなく、5種類をそろえることと、{names[0]}と{names[1]}が出る場所を"
            "選ぶことが勝ちやすさに効いています（街と発展カードに要る資源です）。"
            if ja
            else f"Beyond raw numbers, covering all five resources and picking spots that produce "
            f"{names[0].lower()} and {names[1].lower()} matter (those build towns and development "
            "cards)."
        )
    else:
        start_lesson = (
            f"{names[0]}と{names[1]}が出る場所を選ぶことが勝ちやすさに効いています。"
            if ja
            else f"Spots producing {names[0].lower()} and {names[1].lower()} help the most."
        )
    sp = s["start_port"]
    return {
        "games": f"{s['games']:,}",
        "seat1": pct(first["rate"]),
        "bonus_share": pct(1 - winners_neither, 0),
        "ore_gap": f"{ore_gap * 100:+.1f}" + ("ポイント" if ja else " pts"),
        "seat_text": seat_text,
        "seat_bars": seat_bars,
        "seat_lesson": seat_lesson,
        "winner_vp": f"{s['winner_vp']:.1f}",
        "loser_vp": f"{s['loser_vp']:.1f}",
        "points_bars": points_bars,
        "longest_win": pct(bw["longest"]["rate"]),
        "army_win": pct(bw["army"]["rate"]),
        "neither_win": pct(nb),
        "bonus_lesson": bonus_lesson,
        "pips_mean": f"{s['start_pips_mean']:.1f}",
        "pips_bars": bars(pips_rows, 0.4, ref=0.25),
        "kinds5": pct(kinds[5]["rate"]) if 5 in kinds else "—",
        "kinds4": pct(kinds[4]["rate"]) if 4 in kinds else "—",
        "res_table": res_table,
        "start_lesson": start_lesson,
        "port_special": pct(sp["special"]["rate"]),
        "port_generic": pct(sp["generic"]["rate"]),
        "port_none": pct(sp["none"]["rate"]),
        "rounds": f"{s['turns_mean']:.0f}",
        "mid_lead": pct(s["mid_lead"]["rate"]),
        "dev_win": f"{s['dev_bought']['winner_mean']:.1f}",
        "dev_lose": f"{s['dev_bought']['loser_mean']:.1f}",
        "seven": pct(s["seven_share"]),
    }


def fill(html: str, lang: str) -> str:
    s = json.loads(STATS.read_text(encoding="utf-8"))
    check_claims(s)
    for k, v in values(s, lang).items():
        html = html.replace("{{" + k + "}}", v)
    if "{{" in html:
        raise SystemExit("stats: 置き換えていない {{...}} があります")
    return html
