---
name: steward
description: このリポジトリでPRを作る・直す・CIを通す・マージするときの手順。push前の確認とマージの仕方を決めている。
---

# PR の手順（isle-routes-research）

共通の手順（PR の書き方・CI・コンフリクト・マージ）は satou-aaaaa/shared-workflows の `routines/pr.md`。ここにはこのリポジトリだけの決まりを書く（食い違ったらこちらが優先）。

## push する前
1. `python scripts/check.py --quick` を実行する（ruff・整形・slow 以外のテスト）。
   - lint や整形で落ちたら `python scripts/check.py --fix --quick` で直してから見直す。
   - ルールエンジン（`src/isle/`）を触ったときは `--quick` を付けずに全テストを回し、
     `python scripts/random_games.py --games 500` でも止まらず終わるかを見る。
2. 公開ページ（`web/`・`scripts/build_pages.py`・`src/isle/`）を触ったら `python scripts/build_pages.py` で docs/ を作り直し、
   `.claude/skills/ui-check/SKILL.md` の点検（`node scripts/ui_check.mjs`）をする。`src/isle` を変えると対戦ページの写し（docs/py/）も変わる。
3. 市販ゲームの名前・カード名を、コード・画面・README・コミットの題に書いていないかを見る（NOTICE.md）。

## CI
- `.github/workflows/test.yml` が `python scripts/check.py`（公開ページの作り直しの確認・全テスト込み）、UI 点検（`ui` ジョブ）と actionlint を実行する。
- 落ちたら、ローカルで同じ `scripts/check.py` を再現してから直す。テストを飛ばしたり無効にしたりしない。

## マージ
- 共通の手順（`routines/pr.md`）どおり、CI が緑で未解決のレビューが無ければ squash マージしてよい（satou さんにマージを任されている）。
