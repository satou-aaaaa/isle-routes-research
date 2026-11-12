# isle-routes-research（島の交易路）

六角形の島で資源を集め、道・村・街を建てて10点を目指す4人ゲーム「島の交易路」の、強いAIを作る研究プロジェクト。
研究の成果は、プレイヤーが上達するための学習サイト（ルール入門・AIと対戦・初期配置クイズ・コツ集・データ）として公開する。

姉妹プロジェクト: [carcassonne-research](https://github.com/satou-aaaaa/carcassonne-research)（仕組みの多くをここから写している）。

## スコープ

- 4人対戦（人＋AI3人）。基本ルールのみ。最初はプレイヤーどうしの交換なし（銀行・港との交換だけ）。
- 主目的: 強いAI（評価関数＋サイコロを引いて読むMCTS＋自己対戦）の構築と、学びどころの数値化。
- 計画は [docs/ROADMAP.md](docs/ROADMAP.md)、名前・絵の決まりは [NOTICE.md](NOTICE.md)。

## 準備

```bash
bash scripts/setup.sh          # .venv を作り requirements.txt を入れる（何度実行してもよい。Windows は Git Bash で）
python scripts/check.py --quick  # ruff・整形・テスト
python scripts/random_games.py --games 500  # ランダムに打つ対局でエンジンを点検
```

## 中身

| 場所 | 内容 |
|---|---|
| `src/isle/board.py` | 盤面の形（六角形19・頂点54・辺72・港9）と、資源・数字のランダムな並べ方 |
| `src/isle/game.py` | ルールエンジン（`legal_actions()` と `apply()`） |
| `tests/` | ルールのテスト |
| `scripts/check.py` | push 前・CI の確認 |
