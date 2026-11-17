"""公開ページ（docs/ と英語版 docs/en/）をまとめて作り直す。

    python scripts/build_pages.py           # 作り直す
    python scripts/build_pages.py --check   # 作り直した結果がコミット済みの docs/ と同じか（CI用）

- 日本語のページを組み立て、英語版は対訳表 web/i18n/en/<名前>.json で作る（scripts/i18n.py）。
  訳し漏れ・古い訳があると止まる。
  ひな形: python scripts/i18n.py todo <名前> docs/<ページ>
- 対戦ページはブラウザの中で Python（Pyodide）を動かす。src/isle の .py を docs/py/isle/ に写す
  （ページの AI は研究のエンジンと同じもの。手で直さない）。
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_stats  # noqa: E402
import i18n  # noqa: E402
from site_common import FOOTER, nav_html, page  # noqa: E402

DOCS = ROOT / "docs"
WEB = ROOT / "web"
# ブラウザで使うモジュール（webapi が読み込むものだけ）
PY_FILES = (
    "__init__.py",
    "board.py",
    "game.py",
    "features.py",
    "solver.py",
    "agents.py",
    "mcts.py",
    "webapi.py",
)
# docs/ 直下に写す JavaScript（両方の言語のページで共通）
JS_FILES = ("play.js", "play_worker.js")


def write_page(name: str, file: str, html_ja: str, fill=None) -> None:
    """日本語ページから英語ページを作って書き出す。

    fill(html, lang) を渡すと、訳したあとで {{名前}} を言語ごとの値に置き換える（数字の入る文は
    対訳表に {{名前}} のまま載せ、集計が変わっても訳が古くならないようにする）。
    """
    html_en = i18n.to_english_page(
        html_ja.replace(FOOTER["ja"], FOOTER["en"]),
        file,
        name,
        nav_ja=nav_html(file, "ja"),
        nav_en=nav_html(file, "en"),
    )
    if fill:
        html_ja, html_en = fill(html_ja, "ja"), fill(html_en, "en")
    i18n.write_pair(file, html_ja, html_en)


def copy_engine() -> None:
    out = DOCS / "py" / "isle"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for f in PY_FILES:
        shutil.copyfile(ROOT / "src" / "isle" / f, out / f)
    # GitHub Pages の Jekyll は「_」で始まるファイル（__init__.py）を出さないので止める
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")
    (DOCS / "py" / "manifest.json").write_text(json.dumps(list(PY_FILES)) + "\n", encoding="utf-8")
    for js in JS_FILES:
        shutil.copyfile(WEB / js, DOCS / js)


def build_index() -> None:
    body = (WEB / "index_body.html").read_text(encoding="utf-8")
    html = page(
        "index.html",
        "島の交易路 ― 強いAIと学ぶ資源と開拓のゲーム",
        "六角形の島で資源を集め、道・村・街を建てて10点を目指す4人ゲーム「島の交易路」。"
        "研究中の強いAIと対戦して、序盤の置き方や終盤の決め方を学べます。",
        body,
        css=(WEB / "index.css").read_text(encoding="utf-8"),
    )
    write_page("index", "index.html", html)


def build_play() -> None:
    body = (WEB / "play_body.html").read_text(encoding="utf-8")
    html = page(
        "play.html",
        "AIと対戦",
        "「島の交易路」を研究中のAI3人と4人で対戦。サイコロ・建設・交換・発展カードまで遊べて、"
        "AIのおすすめの手や勝ちやすさの見立ても見られます。",
        body,
        css=(WEB / "play.css").read_text(encoding="utf-8"),
        tail='<script src="play.js"></script>\n',
    )
    write_page("play", "play.html", html)
    # 英語ページは docs/en/ にあるので、JS と Python は1つ上を読む
    en = DOCS / "en" / "play.html"
    text = en.read_text(encoding="utf-8")
    en.write_text(text.replace('<script src="play.js">', '<script src="../play.js">'), "utf-8")


def build_rules() -> None:
    html = page(
        "rules.html",
        "ルール入門",
        "「島の交易路」の遊び方: 島と資源、はじめの置き方、手番の流れ、建てるものの費用、7と盗賊、"
        "交換、発展カード、点の数え方。",
        (WEB / "rules_body.html").read_text(encoding="utf-8"),
        css=(WEB / "rules.css").read_text(encoding="utf-8"),
    )
    write_page("rules", "rules.html", html)


def build_stats_page() -> None:
    html = page(
        "stats.html",
        "データで見る",
        "AI どうしの対局から測った「島の交易路」の数字: 先手の有利さ、勝つ人の点の取り方、"
        "最長の道と最大の騎士、はじめの置き方と勝ちやすさ。",
        (WEB / "stats_body.html").read_text(encoding="utf-8"),
        css=(WEB / "stats.css").read_text(encoding="utf-8"),
    )
    write_page("stats", "stats.html", html, fill=build_stats.fill)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="作り直して git の差分がなければ成功")
    args = ap.parse_args()
    copy_engine()
    build_index()
    build_rules()
    build_play()
    build_stats_page()
    if args.check:
        r = subprocess.run(
            ["git", "status", "--porcelain", "--", "docs/"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        )  # fmt: skip
        if r.stdout.strip():
            print(r.stdout)
            raise SystemExit(
                "docs/ が最新ではありません。"
                "python scripts/build_pages.py を実行してコミットしてください"
            )
        print("docs/ は最新です")


if __name__ == "__main__":
    main()
