# AGENTS.md

オリジナルの4人用資源ゲーム「島の交易路」の強いAIを作る研究リポジトリ。背景と計画は README.md と docs/ROADMAP.md。

## 準備（最初に一度）

```bash
bash scripts/setup.sh   # .venv を作り requirements.txt を入れる（Python の版は .python-version）。何度実行してもよい
```

以後のコマンドは .venv の Python で動かす。Claude Code のクラウドセッションでは `.claude/settings.json` のフックが自動で実行し、.venv を PATH の先頭に置く。

## push する前の確認

```bash
python scripts/check.py --quick   # ruff・整形・slow 以外のテスト
```

このリポジトリだけの PR の決まりは `.claude/skills/steward/SKILL.md`（共通の手順より優先）。

## 名前と権利（必ず守る）

- 市販ゲームの名前・絵・カード名・ルール文を、コード・画面・README・コミットの題に使わない（NOTICE.md）。
- 資源は wood / brick / wool / grain / ore（木材・れんが・羊毛・小麦・鉱石）と一般語で呼ぶ。
- GPL の公開実装のコードは取り込まない（比較相手として別に動かすのはよい）。

## ルールの元

- 基本ルール（3〜4人用の公式ルールブック 2015年版）の数値に合わせる。数値はテスト（tests/test_rules.py）で固定している。
- ルールを変えたら、テストと docs/ROADMAP.md の「ルールの要点」を同じ PR で直す。

## 共通のきまり

- PR の作り方・マージの仕方は satou-aaaaa/shared-workflows の `routines/pr.md`、全体のきまりは `routines/common.md` に従う。
- CI の部品（CI失敗Issue・ブランチ片付け・準備の確認）は shared-workflows の共通部品を呼ぶ。
  リポジトリ側の .github/workflows には呼び出しと設定値だけを書く。
- Claude 以外の AI・人が作業するときは、shared-workflows の `routines/tool-map.md` と `routines/without-claude.md` を読む。
