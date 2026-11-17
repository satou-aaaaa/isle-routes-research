"""対戦ページの窓口（isle.webapi）のテスト。ブラウザでも同じ Python が動く。"""

from __future__ import annotations

import json
import random

from isle import webapi
from isle.webapi import Session


def _play(s: Session, rng: random.Random, max_steps: int = 20000) -> None:
    for _ in range(max_steps):
        st = s.state()
        if st["phase"] == "over":
            return
        if st["to_act"] == s.human:
            assert st["legal"], "人の番なのに打てる手がない"
            s.act(rng.choice(st["legal"]))
        else:
            assert st["legal"] == []
            assert s.ai_step() is not None
    raise AssertionError("終わらない")


def test_full_game_with_random_human():
    s = Session(seed=3, human=1)
    _play(s, random.Random(3))
    assert s.state()["winner"] is not None or s.g.turns >= 1000


def test_state_hides_opponent_cards():
    s = Session(seed=5, human=0)
    rng = random.Random(5)
    for _ in range(300):
        if s.state()["phase"] == "over":
            break
        if s.g.to_act == 0:
            s.act(rng.choice(s.state()["legal"]))
        else:
            s.ai_step()
    st = s.state()
    assert "hand" in st["players"][0]
    if st["winner"] is None:
        for q in (1, 2, 3):
            p = st["players"][q]
            assert "hand" not in p and "dev" not in p
            assert p["vp"] == p["vp_public"]
    assert "dev_deck" not in json.dumps(st)


def test_illegal_action_is_rejected():
    out = json.loads(webapi.js_new(json.dumps({"seed": 7, "human": 0})))
    assert out["state"]["to_act"] == 0
    r = json.loads(webapi.js_act(json.dumps(["end"])))
    assert "error" in r
    assert json.loads(webapi.js_state())["phase"] == "setup_settle"


def test_js_round_trip_and_hint():
    out = json.loads(webapi.js_new(json.dumps({"seed": 11, "human": 2, "level": "normal"})))
    b = out["board"]
    assert len(b["hexes"]) == 19 and len(b["vertices"]) == 54 and len(b["edges"]) == 72
    assert len(b["ports"]) == 9
    # 人の番まで AI を進める
    while json.loads(webapi.js_state())["to_act"] != 2:
        json.loads(webapi.js_ai_step())
    h = json.loads(webapi.js_hint())
    st = json.loads(webapi.js_state())
    assert h["action"] in st["legal"]
    assert abs(sum(st["chances"]) - 1) < 0.01
