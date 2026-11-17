---
name: ui-check
description: 公開ページ（docs/ の対戦ページ・学習ページ）や、それを作る web/・scripts/build_pages.py・src/isle/webapi.py を変えたときに、スマホ幅とPC幅で表示と使いやすさを点検して直す手順。
---

# サイトの UI/UX 点検（isle-routes-research）

サイトの目的は**プレイヤーの上達**。ページを変えたら毎回、同じ作業の中で点検して直す。

## 1. 作り直しと機械の点検（必ず）
```bash
python scripts/build_pages.py                 # docs/ と docs/en/ を作り直す（docs/*.html は手で直さない）
node scripts/ui_check.mjs --shots ui-shots    # 全ページ × スマホ幅390px・PC幅1280px
node scripts/ui_check.mjs play.html           # 1ページだけ
```
- クラウドセッションでは cdn.jsdelivr.net に届かないことがある。そのときは
  `npm pack pyodide@0.26.4 && tar xzf pyodide-0.26.4.tgz` で展開し、`PYODIDE_DIR=<展開先>/package` を付けて実行する。
- ✗ は直す（CI の test.yml `ui` ジョブも同じ点検で落ちる）: コンソールエラー・読み込み失敗、横のはみ出し、
  24px 未満の押す場所、名前のないボタン、言語の自動切り替え、対戦ページで初期配置〜手番2回が打てない。
- △ は目で見て判断する（スマホで高さ 44px 未満、12px 未満の文字、横スクロールが要る表）。

## 2. 目で見る点検（ui-shots/*.png）
- 対戦ページ: 盤・置ける丸・決定ボタン・手札がスマホで続けて見えるか。PC で盤が画面からはみ出さないか。
- 「AIならどう打つ？」のおすすめが文と盤の赤い丸で分かるか。
- 英語版（en_*.png）: 訳が長くなってボタンや選択欄がはみ出していないか。
- 学びに役立つか: 本文と図の対応、次に読むページへの案内、用語の揺れ（資源は木材・れんが・羊毛・小麦・鉱石）。

## 3. 直し方
- 元（`web/*`, `scripts/build_pages.py`, `scripts/site_common.py`）を直して `python scripts/build_pages.py`。
- 文を変えたら対訳表 `web/i18n/en/<ページ>.json` も直す（訳し漏れ・古い訳があると build_pages が止まる。
  ひな形: `python scripts/i18n.py todo <名前> docs/<ページ>`）。
- 対戦ページの AI は `src/isle` をそのまま Pyodide で動かす（`docs/py/` は写し）。ルールや AI を変えたら作り直す。
