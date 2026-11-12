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
python scripts/run_match.py --agents greedy,random,random,random --games 20  # 勝率（基準は25%）
```

## 中身

| 場所 | 内容 |
|---|---|
| `src/isle/board.py` | 盤面の形（六角形19・頂点54・辺72・港9）と、資源・数字のランダムな並べ方 |
| `src/isle/game.py` | ルールエンジン（`legal_actions()` と `apply()`、探索用の速い `clone()`） |
| `src/isle/features.py` | 盤面の特徴量と評価関数（手で決めた最初の重み） |
| `src/isle/agents.py` | AI: ランダム、評価関数で1手先を選ぶ貪欲AI（山札はのぞかない）、勝てる手番を逃さない `greedy_win`（いまの最強） |
| `src/isle/arena.py` | 対局の実行・記録（seed と手の列で再現）・席を入れ替えた成績 |
| `src/isle/solver.py` | 手番の中を読み切り、この手番で勝てる筋を探す厳密ソルバー |
| `scripts/gto_turn_check.py` | 「勝てる手番を逃した」回数を数える |
| `src/isle/models.py` | 評価関数の重みの保存と読み込み（`models/*.json`） |
| `scripts/run_match.py` | 4人の対局を席を入れ替えて回し、勝率を出す |
| `scripts/tune_spsa.py` | 対局の勝ち負けから重みを直接合わせる（SPSA） |
| `tests/` | ルールのテスト |
| `scripts/check.py` | push 前・CI の確認 |
