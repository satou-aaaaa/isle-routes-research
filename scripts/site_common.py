"""公開ページ（docs/）の共通部品: 色・文字・ナビ・ページの外枠。

ページは日本語で組み立て、英語版は対訳表（web/i18n/en/<名前>.json）で作る（scripts/i18n.py）。
色はトークン（:root の変数）で決め、暗い画面の設定でも読めるようにする。
"""

from __future__ import annotations

from pathlib import Path

from i18n import lang_link

SITE_NAME = {"ja": "島の交易路", "en": "Isle Routes"}
# (ファイル名, 日本語, 英語)。ナビに並べる順
PAGES = [
    ("index.html", "トップ", "Home"),
    ("play.html", "AIと対戦", "Play the AI"),
]

FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
    "family=Zen+Kaku+Gothic+New:wght@400;500;700"
    '&family=Zen+Maru+Gothic:wght@700&display=swap">'
)

BASE_CSS = (Path(__file__).resolve().parents[1] / "web" / "base.css").read_text(encoding="utf-8")

FOOTER = {
    "ja": (
        '<footer class="site">「島の交易路」はこの研究のためのオリジナルの名前です。'
        "AI とページのソースは "
        '<a href="https://github.com/satou-aaaaa/isle-routes-research">GitHub</a>'
        " にあります。</footer>"
    ),
    "en": (
        '<footer class="site">"Isle Routes" is an original name made for this research project. '
        "The source code of the AI and these pages is on "
        '<a href="https://github.com/satou-aaaaa/isle-routes-research">GitHub</a>.</footer>'
    ),
}


def nav_html(current: str, lang: str = "ja") -> str:
    aria = "サイト内のページ" if lang == "ja" else "Site pages"
    links = []
    for href, ja, en in PAGES[1:]:
        cur = ' aria-current="page"' if href == current else ""
        links.append(f'<a class="p" href="{href}"{cur}>{ja if lang == "ja" else en}</a>')
    return (
        f'<nav class="site" aria-label="{aria}">'
        f'<a class="home" href="index.html">{SITE_NAME[lang]}</a>'
        + "".join(links)
        + lang_link(current, lang, "p lang")
        + "</nav>"
    )


def page(
    current: str, title: str, desc: str, body: str, css: str = "", head: str = "", tail: str = ""
) -> str:
    """日本語ページの HTML。英語版は i18n.to_english_page で作る。"""
    full_title = title if current == "index.html" else f"{title} | {SITE_NAME['ja']}"
    return (
        '<!doctype html>\n<html lang="ja">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{full_title}</title>\n"
        f'<meta name="description" content="{desc}">\n'
        f"{FONTS}\n<style>{BASE_CSS}{css}</style>\n{head}</head>\n<body>\n"
        f'<div class="wrap">\n{nav_html(current, "ja")}\n{body}\n{FOOTER["ja"]}\n</div>\n'
        f"{tail}</body>\n</html>\n"
    )
