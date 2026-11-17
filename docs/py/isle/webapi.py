"""ブラウザの対戦ページ（docs/play.html）から使う窓口。

対戦ページはブラウザの中で Python（Pyodide）を動かし、このモジュールをそのまま使う。
ルールと AI を JavaScript に移さないので、研究で使うエンジンとページの動きがずれない。

やり取りはすべて JSON の文字列（JavaScript 側で JSON.parse する）。
人の席から見えない情報（相手の手札の中身・発展カードの中身・山の順番）は state() に出さない。
"""

from __future__ import annotations

import json
import math
import random

from .agents import WinCheckAgent
from .board import PORT_EDGES, TOPO
from .features import evaluate
from .game import (
    DISCARD,
    FREE_ROAD,
    MAIN,
    OVER,
    PRE_ROLL,
    ROBBER,
    SETUP_ROAD,
    SETUP_SETTLE,
    STEAL,
    VP_CARD,
    WIN_VP,
    Game,
)
from .mcts import MCTSAgent

PHASE_NAMES = {
    SETUP_SETTLE: "setup_settle",
    SETUP_ROAD: "setup_road",
    PRE_ROLL: "pre_roll",
    DISCARD: "discard",
    ROBBER: "robber",
    STEAL: "steal",
    MAIN: "main",
    FREE_ROAD: "free_road",
    OVER: "over",
}
LEVELS = ("normal", "strong")


def make_ai(level: str, seed: int):
    if level == "strong":
        return MCTSAgent(seed=seed, sims=32)
    return WinCheckAgent(seed=seed)


def win_chances(g: Game, temp: float = 1.0) -> list[float]:
    """評価関数を softmax にした「勝ちやすさ」の目安（MCTS の葉と同じ式）。

    見えない札も含めた評価なので、ページでは「AIの見立て」として目安だけを出す。
    """
    if g.winner is not None:
        return [1.0 if q == g.winner else 0.0 for q in range(g.n)]
    vals = [evaluate(g, q) for q in range(g.n)]
    m = max(vals)
    ex = [math.exp((v - m) / temp) for v in vals]
    s = sum(ex)
    return [round(x / s, 3) for x in ex]


class Session:
    """1局ぶん。human は人の席（0〜3）。"""

    def __init__(self, seed: int | None = None, human: int = 0, level: str = "normal"):
        if seed is None:
            seed = random.randrange(1 << 30)
        if level not in LEVELS:
            raise ValueError(f"level は {LEVELS} のどれか")
        self.seed = seed
        self.human = human
        self.level = level
        self.g = Game(seed=seed)
        self.ai = {q: make_ai(level, seed * 10 + q) for q in range(4) if q != human}
        self.log: list[dict] = []

    # ---- 見せる情報 ----
    def board(self) -> dict:
        """盤の形（局の間で変わらない）と、この局の資源・数字・港。"""
        lay = self.g.layout
        ports = []
        for e, kind in zip(PORT_EDGES, lay.ports, strict=True):
            a, b = TOPO.edges[e]
            ports.append({"edge": e, "kind": kind, "v": [a, b]})
        return {
            "seed": self.seed,
            "human": self.human,
            "level": self.level,
            "hexes": [
                {"x": x, "y": y, "terrain": t, "number": n}
                for (x, y), t, n in zip(TOPO.hex_xy, lay.terrain, lay.number, strict=True)
            ],
            "vertices": [list(xy) for xy in TOPO.vertex_xy],
            "edges": [list(e) for e in TOPO.edges],
            "ports": ports,
            "win_vp": WIN_VP,
        }

    def _player(self, q: int) -> dict:
        g, pl = self.g, self.g.players[q]
        me = q == self.human or g.winner is not None
        d = {
            "vp": g.vp(q, hidden=me),
            "vp_public": g.vp(q, hidden=False),
            "cards": pl.cards(),
            "dev_count": sum(pl.dev),
            "knights": pl.knights,
            "roads": pl.roads,
            "settlements": pl.settlements,
            "cities": pl.cities,
            "road_len": g.longest_len[q],
        }
        if me:
            d["hand"] = list(pl.hand)
            d["dev"] = list(pl.dev)
            d["dev_new"] = list(pl.dev_new)
            d["vp_cards"] = pl.dev[VP_CARD]
        return d

    def state(self) -> dict:
        g = self.g
        s = {
            "phase": PHASE_NAMES[g.phase],
            "current": g.current,
            "to_act": g.to_act if g.phase != OVER else -1,
            "turns": g.turns,
            "last_roll": g.last_roll,
            "robber": g.robber,
            "building": list(g.building),
            "is_city": list(g.is_city),
            "road": list(g.road),
            "players": [self._player(q) for q in range(g.n)],
            "longest": g.longest_holder,
            "army": g.army_holder,
            "winner": g.winner,
            "bank": list(g.bank),
            "deck": len(g.dev_deck),
            "dev_played": g.dev_played,
            "free_roads": g.free_roads,
            "chances": win_chances(g),
            "legal": [],
        }
        if g.phase == DISCARD:
            s["discard_left"] = g.discard_queue[0][1]
        if g.phase != OVER and g.to_act == self.human:
            s["legal"] = [list(a) for a in g.legal_actions()]
            s["ratios"] = g._trade_ratios(self.human)
        return s

    # ---- 進める ----
    def _apply(self, q: int, a: tuple) -> dict:
        g = self.g
        before = [list(pl.hand) for pl in g.players]
        dev_before = list(g.players[q].dev)
        cur = g.current
        g.apply(a)
        ev = {"who": q, "action": list(a), "turn": g.turns}
        if a[0] == "roll":
            ev["roll"] = g.last_roll
            gains = [
                [max(0, x - y) for x, y in zip(pl.hand, b, strict=True)]
                for pl, b in zip(g.players, before, strict=True)
            ]
            ev["gains"] = gains  # 産出は公開の情報
        elif a[0] == "steal":
            victim = a[1]
            if self.human in (cur, victim):
                diff = [x - y for x, y in zip(g.players[cur].hand, before[cur], strict=True)]
                ev["stolen"] = next((r for r, x in enumerate(diff) if x > 0), None)
        elif a[0] == "buy_dev" and q == self.human:
            diff = [x - y for x, y in zip(g.players[q].dev, dev_before, strict=True)]
            ev["card"] = next((c for c, x in enumerate(diff) if x > 0), None)
        elif a[0] == "monopoly":
            ev["got"] = g.players[cur].hand[a[1]] - before[cur][a[1]]
        if g.winner is not None:
            ev["winner"] = g.winner
        self.log.append(ev)
        return ev

    def act(self, a: list) -> dict:
        """人の手を打つ。合法でなければ ValueError。"""
        g = self.g
        if g.phase == OVER or g.to_act != self.human:
            raise ValueError("人の番ではありません")
        t = tuple(a)
        if t not in g.legal_actions():
            raise ValueError(f"打てない手です: {a}")
        return self._apply(self.human, t)

    def ai_step(self) -> dict | None:
        """AI の番なら1手進める。人の番か終局なら None。"""
        g = self.g
        if g.phase == OVER or g.to_act == self.human:
            return None
        q = g.to_act
        a = self.ai[q].act(g)
        return self._apply(q, a)

    def hint(self) -> dict | None:
        """人の番で、強いAI（MCTS）ならどう打つか。手番の中は候補ごとの見積もりも返す。"""
        g = self.g
        if g.phase == OVER or g.to_act != self.human:
            return None
        helper = MCTSAgent(seed=len(self.log) + 1, sims=48)
        a = helper.act(g.clone())
        out = {"action": list(a)}
        if g.phase == MAIN:
            acts = g.legal_actions()
            cands = helper.candidates(g, acts)
            out["candidates"] = [list(c) for c in cands]
        return out


# ---- JavaScript から呼ぶ関数（引数も返り値も JSON の文字列） ----
_session: Session | None = None


def js_new(opts: str) -> str:
    global _session
    o = json.loads(opts)
    _session = Session(
        seed=o.get("seed"), human=int(o.get("human", 0)), level=o.get("level", "normal")
    )
    return json.dumps({"board": _session.board(), "state": _session.state()})


def js_state() -> str:
    assert _session is not None
    return json.dumps(_session.state())


def js_act(a: str) -> str:
    assert _session is not None
    try:
        ev = _session.act(json.loads(a))
    except ValueError as e:
        return json.dumps({"error": str(e), "state": _session.state()})
    return json.dumps({"event": ev, "state": _session.state()})


def js_ai_step() -> str:
    assert _session is not None
    ev = _session.ai_step()
    return json.dumps({"event": ev, "state": _session.state()})


def js_hint() -> str:
    assert _session is not None
    return json.dumps(_session.hint())
