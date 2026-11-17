// 「島の交易路」AIと対戦（docs/play.html と docs/en/play.html で共通）。
// ルールと AI は Web Worker の中の Python（src/isle をそのまま）が持ち、ここは表示と操作だけ。
(function () {
  "use strict";
  const LANG = document.documentElement.lang === "en" ? "en" : "ja";
  // 英語ページ（docs/en/）からも docs/ の worker と Python を読むので、この JS の場所を基準にする
  const BASE = document.currentScript ? document.currentScript.src : location.href;
  const T = {
    ja: {
      res: ["木材", "れんが", "羊毛", "小麦", "鉱石"],
      dev: ["騎士", "得点", "道づくり", "収穫", "独占"],
      you: "あなた",
      ai: (q) => `AI ${q}`,
      loading: "AIを準備しています（初回は20秒ほどかかります）…",
      loadFail: "AIを読み込めませんでした。通信を確かめて、ページを読み直してください。",
      thinking: (n) => `${n} が考えています…`,
      yourTurn: "あなたの番です",
      phase: {
        setup_settle: "最初の村を置く頂点を選んでください",
        setup_road: "村につなげる道を選んでください",
        pre_roll: "サイコロを振ってください（騎士はサイコロの前にも使えます）",
        discard: (n) => `手札が多いので、あと ${n} 枚捨ててください`,
        robber: "盗賊を動かす土地を選んでください",
        steal: "1枚奪う相手を選んでください",
        main: "建てる・交換する・カードを使う、終わったら「手番を終える」",
        free_road: (n) => `道づくり: 無料の道をあと ${n} 本選んでください`,
      },
      roll: "サイコロを振る",
      end: "手番を終える",
      buyDev: "発展カードを買う",
      trade: "銀行と交換",
      give: "出す",
      get: "もらう",
      cancel: "やめる",
      confirm: "決定",
      buildHere: {
        settle: "ここに村を置く",
        road: "ここに道を置く",
        build_road: "道を建てる（木材＋れんが）",
        build_settlement: "村を建てる（木材＋れんが＋羊毛＋小麦）",
        build_city: "街にする（小麦2＋鉱石3）",
        free_road: "ここに無料の道",
        robber: "ここに盗賊を置く",
      },
      play: "使う",
      hint: "AIならどう打つ？",
      hintWait: "AIが読んでいます…",
      hintIs: "AIのおすすめ",
      newGame: "新しい対局",
      level: "AIの強さ",
      levels: { normal: "ふつう（貪欲＋勝ち筋読み）", strong: "強い（サイコロを引いて読む探索）" },
      seat: "あなたの席",
      seats: ["1番手", "2番手", "3番手", "4番手"],
      start: "対局を始める",
      vp: "点",
      cards: "手札",
      devs: "発展",
      knights: "騎士",
      roadLen: "道",
      longest: "最長の道",
      army: "最大の騎士",
      chances: "AIの見立て（勝ちやすさの目安）",
      log: "これまでの流れ",
      hand: "あなたの手札",
      myDev: "あなたの発展カード",
      newCard: "（この番に買った）",
      winner: (n) => `${n} の勝ち！`,
      youWin: "あなたの勝ちです！",
      breakdown: "点の内訳",
      bd: ["村", "街", "最長の道", "最大の騎士", "得点カード", "合計"],
      again: "もう一局",
      ev: {
        settle: "村を置いた",
        road: "道を置いた",
        roll: (d) => `サイコロ ${d}`,
        discard: (r) => `${r}を1枚捨てた`,
        robber: "盗賊を動かした",
        steal: (n, r) => (r == null ? `${n} から1枚奪った` : `${n} から${r}を奪った`),
        build_road: "道を建てた",
        build_settlement: "村を建てた",
        build_city: "街にした",
        buy_dev: (c) => (c == null ? "発展カードを買った" : `発展カードを買った（${c}）`),
        knight: "騎士を使った",
        road_building: "道づくりを使った",
        plenty: (a, b) => `収穫を使った（${a}・${b}）`,
        monopoly: (r, n) => `独占を使った（${r}を${n}枚）`,
        free_road: "無料の道を置いた",
        trade: (a, n, b) => `${a}${n}枚を${b}に交換`,
        end: "手番を終えた",
        gains: (list) => `もらった: ${list}`,
      },
      hintAct: {
        steal: (n) => `${n} から1枚奪う`,
        discard: (r) => `${r}を捨てる`,
        trade: (a, n, b) => `${a}${n}枚を${b}に交換する`,
        mark: "（盤の赤い丸）",
      },
      pickTwo: "収穫: もらう資源を2つ選んでください",
      pickOne: "独占: 集める資源を選んでください",
      noMoves: "（打てる手はありません）",
      robberNote: "7 が出ました",
    },
    en: {
      res: ["Wood", "Brick", "Wool", "Grain", "Ore"],
      dev: ["Knight", "Point", "Road building", "Plenty", "Monopoly"],
      you: "You",
      ai: (q) => `AI ${q}`,
      loading: "Getting the AI ready (about 20 seconds the first time)…",
      loadFail: "Could not load the AI. Check your connection and reload the page.",
      thinking: (n) => `${n} is thinking…`,
      yourTurn: "Your turn",
      phase: {
        setup_settle: "Pick a corner for your starting village",
        setup_road: "Pick a road next to the village",
        pre_roll: "Roll the dice (you may play a knight before rolling)",
        discard: (n) => `Too many cards: discard ${n} more`,
        robber: "Pick a land for the robber",
        steal: "Pick a player to take one card from",
        main: "Build, trade or play a card, then end your turn",
        free_road: (n) => `Road building: pick ${n} more free road(s)`,
      },
      roll: "Roll the dice",
      end: "End turn",
      buyDev: "Buy a development card",
      trade: "Trade with the bank",
      give: "Give",
      get: "Get",
      cancel: "Cancel",
      confirm: "OK",
      buildHere: {
        settle: "Place the village here",
        road: "Place the road here",
        build_road: "Build road (wood + brick)",
        build_settlement: "Build village (wood + brick + wool + grain)",
        build_city: "Upgrade to town (2 grain + 3 ore)",
        free_road: "Free road here",
        robber: "Move the robber here",
      },
      play: "Play",
      hint: "What would the AI do?",
      hintWait: "The AI is thinking…",
      hintIs: "AI suggests",
      newGame: "New game",
      level: "AI strength",
      levels: { normal: "Normal (greedy + finds winning lines)", strong: "Strong (search that samples dice)" },
      seat: "Your seat",
      seats: ["1st", "2nd", "3rd", "4th"],
      start: "Start the game",
      vp: "pts",
      cards: "Cards",
      devs: "Dev",
      knights: "Knights",
      roadLen: "Road",
      longest: "Longest road",
      army: "Largest army",
      chances: "AI's view (rough chance to win)",
      log: "Game log",
      hand: "Your cards",
      myDev: "Your development cards",
      newCard: "(bought this turn)",
      winner: (n) => `${n} wins!`,
      youWin: "You win!",
      breakdown: "Where the points came from",
      bd: ["Villages", "Towns", "Longest road", "Largest army", "Point cards", "Total"],
      again: "Play again",
      ev: {
        settle: "placed a village",
        road: "placed a road",
        roll: (d) => `rolled ${d}`,
        discard: (r) => `discarded 1 ${r}`,
        robber: "moved the robber",
        steal: (n, r) => (r == null ? `took a card from ${n}` : `took ${r} from ${n}`),
        build_road: "built a road",
        build_settlement: "built a village",
        build_city: "upgraded to a town",
        buy_dev: (c) => (c == null ? "bought a development card" : `bought a development card (${c})`),
        knight: "played a knight",
        road_building: "played road building",
        plenty: (a, b) => `played plenty (${a}, ${b})`,
        monopoly: (r, n) => `played monopoly (${n} ${r})`,
        free_road: "placed a free road",
        trade: (a, n, b) => `traded ${n} ${a} for ${b}`,
        end: "ended the turn",
        gains: (list) => `received: ${list}`,
      },
      hintAct: {
        steal: (n) => `take a card from ${n}`,
        discard: (r) => `discard ${r}`,
        trade: (a, n, b) => `trade ${n} ${a} for ${b}`,
        mark: "(red circle on the board)",
      },
      pickTwo: "Plenty: pick two resources",
      pickOne: "Monopoly: pick a resource to collect",
      noMoves: "(no moves)",
      robberNote: "A 7 was rolled",
    },
  }[LANG];

  const TERRAIN = ["#3f7d3a", "#b5562d", "#9fd06a", "#e7c24a", "#8b919b"];
  const DESERT = "#dcc9a0";
  const PCOL = ["#d64545", "#2f6fb5", "#8a4fbf", "#e08a12"];
  const RES_ICON = ["🌲", "🧱", "🐑", "🌾", "⛰️"];

  const $ = (id) => document.getElementById(id);
  const el = (tag, attrs, ...kids) => {
    const n = document.createElement(tag);
    for (const k in attrs || {}) {
      if (k === "class") n.className = attrs[k];
      else if (k.startsWith("on")) n.addEventListener(k.slice(2), attrs[k]);
      else n.setAttribute(k, attrs[k]);
    }
    for (const c of kids) if (c != null) n.append(c);
    return n;
  };
  const SVG = "http://www.w3.org/2000/svg";
  const sv = (tag, attrs) => {
    const n = document.createElementNS(SVG, tag);
    for (const k in attrs) n.setAttribute(k, attrs[k]);
    return n;
  };

  // ---- Python との通信 ----
  let worker = null;
  let seq = 0;
  const waiting = new Map();
  function call(fn, arg) {
    return new Promise((resolve, reject) => {
      const id = ++seq;
      waiting.set(id, { resolve, reject });
      worker.postMessage({ id, fn, arg });
    });
  }
  function startWorker() {
    worker = new Worker(new URL("play_worker.js", BASE));
    worker.onmessage = (e) => {
      const w = waiting.get(e.data.id);
      if (!w) return;
      waiting.delete(e.data.id);
      if (e.data.ok) w.resolve(e.data.data);
      else w.reject(new Error(e.data.error));
    };
  }

  // ---- 状態 ----
  let board = null;
  let st = null;
  let busy = false;
  let pending = null; // 盤で選んだ手（決定を待つ）
  let mode = null; // "trade" | "plenty" | "monopoly"
  let tradeGive = null;
  let plentyPick = [];
  let hintAct = null;
  const logItems = [];

  const name = (q) => (q === board.human ? T.you : T.ai(q));
  const legal = () => (st && st.legal) || [];
  const has = (kind) => legal().some((a) => a[0] === kind);
  const sameAct = (a, b) => a && b && a.length === b.length && a.every((x, i) => x === b[i]);

  // ---- 盤 ----
  function hexPoints(x, y, s) {
    const pts = [];
    for (let k = 0; k < 6; k++) {
      const ang = ((60 * k - 30) * Math.PI) / 180;
      pts.push(`${(x + s * Math.cos(ang)).toFixed(3)},${(y + s * Math.sin(ang)).toFixed(3)}`);
    }
    return pts.join(" ");
  }

  function drawBoard() {
    const svg = $("board");
    svg.textContent = "";
    svg.append(sv("rect", { x: -6.4, y: -5.6, width: 12.8, height: 11.2, class: "sea", rx: 0.6 }));
    // 港
    for (const p of board.ports) {
      const [a, b] = p.v.map((v) => board.vertices[v]);
      const mx = (a[0] + b[0]) / 2;
      const my = (a[1] + b[1]) / 2;
      const len = Math.hypot(mx, my);
      const px = mx + (mx / len) * 0.75;
      const py = my + (my / len) * 0.75;
      svg.append(sv("line", { x1: a[0], y1: a[1], x2: px, y2: py, class: "pier" }));
      svg.append(sv("line", { x1: b[0], y1: b[1], x2: px, y2: py, class: "pier" }));
      const g = sv("g", { class: "port" });
      g.append(sv("circle", { cx: px, cy: py, r: 0.42, fill: p.kind === 5 ? "#fff" : TERRAIN[p.kind] }));
      const t = sv("text", { x: px, y: py + (p.kind === 5 ? 0.09 : 0.25), class: "port-t" + (p.kind === 5 || p.kind === 2 || p.kind === 3 ? " dark" : "") });
      t.textContent = p.kind === 5 ? "3:1" : "2:1";
      g.append(t);
      if (p.kind !== 5) {
        const ic = sv("text", { x: px, y: py - 0.13, class: "port-i" });
        ic.textContent = RES_ICON[p.kind];
        g.append(ic);
      }
      const title = sv("title", {});
      title.textContent = p.kind === 5 ? "3:1" : `2:1 ${T.res[p.kind]}`;
      g.append(title);
      svg.append(g);
    }
    // 土地
    board.hexes.forEach((h, i) => {
      const g = sv("g", { class: "hex", "data-hex": i });
      g.append(sv("polygon", { points: hexPoints(h.x, h.y, 0.98), fill: h.terrain < 0 ? DESERT : TERRAIN[h.terrain] }));
      if (h.terrain >= 0) {
        const ic = sv("text", { x: h.x, y: h.y - 0.38, class: "hex-icon" });
        ic.textContent = RES_ICON[h.terrain];
        g.append(ic);
      }
      if (h.number) {
        g.append(sv("circle", { cx: h.x, cy: h.y + 0.12, r: 0.36, class: "chip" }));
        const t = sv("text", { x: h.x, y: h.y + 0.25, class: "num" + (h.number === 6 || h.number === 8 ? " hot" : "") });
        t.textContent = h.number;
        g.append(t);
        const dots = 6 - Math.abs(7 - h.number);
        const d = sv("text", { x: h.x, y: h.y + 0.43, class: "pips" + (h.number === 6 || h.number === 8 ? " hot" : "") });
        d.textContent = "•".repeat(dots);
        g.append(d);
      }
      const title = sv("title", {});
      title.textContent = h.terrain < 0 ? "—" : `${T.res[h.terrain]} ${h.number}`;
      g.append(title);
      g.addEventListener("click", () => pick(["robber", i]));
      svg.append(g);
    });
    svg.append(sv("g", { id: "layer-roads" }));
    svg.append(sv("g", { id: "layer-buildings" }));
    svg.append(sv("g", { id: "layer-robber" }));
    svg.append(sv("g", { id: "layer-targets" }));
  }

  function drawPieces() {
    const roads = $("layer-roads");
    const blds = $("layer-buildings");
    const rob = $("layer-robber");
    roads.textContent = blds.textContent = rob.textContent = "";
    st.road.forEach((q, e) => {
      if (q < 0) return;
      const [a, b] = board.edges[e].map((v) => board.vertices[v]);
      roads.append(sv("line", { x1: a[0], y1: a[1], x2: b[0], y2: b[1], class: "road", stroke: PCOL[q] }));
    });
    st.building.forEach((q, v) => {
      if (q < 0) return;
      const [x, y] = board.vertices[v];
      if (st.is_city[v]) {
        blds.append(sv("rect", { x: x - 0.25, y: y - 0.25, width: 0.5, height: 0.5, rx: 0.06, fill: PCOL[q], class: "bld" }));
      } else {
        blds.append(sv("circle", { cx: x, cy: y, r: 0.2, fill: PCOL[q], class: "bld" }));
      }
    });
    const h = board.hexes[st.robber];
    rob.append(sv("circle", { cx: h.x + 0.42, cy: h.y - 0.05, r: 0.22, class: "robber" }));
    // 選べる所
    const tg = $("layer-targets");
    tg.textContent = "";
    if (busy || st.to_act !== board.human) return;
    const show = (a, x, y, kind) => {
      const isPending = sameAct(a, pending);
      const isHint = sameAct(a, hintAct);
      const c = sv("circle", {
        cx: x,
        cy: y,
        r: kind === "edge" ? 0.17 : 0.24,
        class: "target" + (isPending ? " sel" : "") + (isHint ? " hint" : ""),
        tabindex: 0,
        role: "button",
        "aria-label": T.buildHere[a[0]] || a[0],
      });
      c.addEventListener("click", (e) => {
        e.stopPropagation();
        pick(a);
      });
      c.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          pick(a);
        }
      });
      tg.append(c);
    };
    for (const a of legal()) {
      if (a[0] === "settle" || a[0] === "build_settlement" || a[0] === "build_city") {
        const [x, y] = board.vertices[a[1]];
        show(a, x, y, "v");
      } else if (a[0] === "road" || a[0] === "build_road" || a[0] === "free_road") {
        const [p, q] = board.edges[a[1]].map((v) => board.vertices[v]);
        show(a, (p[0] + q[0]) / 2, (p[1] + q[1]) / 2, "edge");
      } else if (a[0] === "robber") {
        const hx = board.hexes[a[1]];
        show(a, hx.x, hx.y + 0.12, "hex");
      }
    }
  }

  // ---- 操作 ----
  function pick(a) {
    if (busy || !legal().some((b) => sameAct(a, b))) return;
    pending = sameAct(a, pending) ? null : a;
    render();
  }

  async function act(a) {
    if (busy) return;
    pending = null;
    mode = null;
    tradeGive = null;
    plentyPick = [];
    hintAct = null;
    $("hint-out").textContent = "";
    busy = true;
    try {
      const r = await call("act", a);
      if (r.error) console.warn(r.error);
      if (r.event) addLog(r.event);
      st = r.state;
    } finally {
      busy = false;
    }
    render();
    runAI();
  }

  async function runAI() {
    while (st && st.phase !== "over" && st.to_act !== board.human) {
      busy = true;
      $("status").textContent = T.thinking(name(st.to_act));
      render(true);
      await new Promise((r) => setTimeout(r, speed()));
      const r = await call("ai", null);
      if (r.event) addLog(r.event);
      st = r.state;
    }
    busy = false;
    render();
  }

  function speed() {
    const s = $("speed");
    return s ? Number(s.value) : 350;
  }

  // ---- 記録 ----
  function resList(arr) {
    return arr
      .map((n, r) => (n ? (LANG === "en" ? `${n} ${T.res[r]}` : `${T.res[r]}${n}`) : ""))
      .filter(Boolean)
      .join(LANG === "en" ? ", " : "・");
  }
  function describe(ev) {
    const a = ev.action;
    const E = T.ev;
    switch (a[0]) {
      case "roll": {
        let s = E.roll(ev.roll);
        const mine = ev.gains && ev.gains[board.human];
        if (mine && mine.some((x) => x)) s += " / " + E.gains(resList(mine));
        return s;
      }
      case "discard":
        return E.discard(T.res[a[1]]);
      case "steal":
        return E.steal(name(a[1]), ev.stolen == null ? null : T.res[ev.stolen]);
      case "buy_dev":
        return E.buy_dev(ev.card == null ? null : T.dev[ev.card]);
      case "plenty":
        return E.plenty(T.res[a[1]], T.res[a[2]]);
      case "monopoly":
        return E.monopoly(T.res[a[1]], ev.got);
      case "trade": {
        const ratio = ev.who === board.human && st && st.ratios ? st.ratios[a[1]] : "";
        return E.trade(T.res[a[1]], ratio, T.res[a[2]]);
      }
      default:
        return typeof E[a[0]] === "string" ? E[a[0]] : a[0];
    }
  }
  function addLog(ev) {
    if (ev.action[0] === "end" && ev.who !== board.human) return;
    logItems.push({ who: ev.who, text: describe(ev), roll7: ev.roll === 7 });
    if (logItems.length > 80) logItems.shift();
  }

  // ---- 表示 ----
  function render(aiTurn) {
    drawPieces();
    renderPlayers();
    renderChances();
    renderHand();
    renderActions(aiTurn);
    renderLog();
    if (st.phase === "over") renderOver();
  }

  function renderPlayers() {
    const box = $("players");
    box.textContent = "";
    st.players.forEach((p, q) => {
      const badges = [];
      if (st.longest === q) badges.push(el("span", { class: "badge" }, T.longest));
      if (st.army === q) badges.push(el("span", { class: "badge" }, T.army));
      box.append(
        el(
          "div",
          { class: "pl" + (st.current === q && st.phase !== "over" ? " cur" : "") + (q === board.human ? " me" : "") },
          el("span", { class: "dot", style: `background:${PCOL[q]}` }),
          el("b", {}, name(q)),
          el("span", { class: "vp" }, `${p.vp} ${T.vp}`),
          el(
            "small",
            {},
            `${T.cards} ${p.cards} · ${T.devs} ${p.dev_count} · ${T.knights} ${p.knights} · ${T.roadLen} ${p.road_len}`,
          ),
          ...badges,
        ),
      );
    });
  }

  function renderChances() {
    const box = $("chances");
    box.textContent = "";
    st.chances.forEach((c, q) => {
      const pct = Math.round(c * 100);
      box.append(
        el(
          "div",
          { class: "bar-row" },
          el("span", { class: "bar-name" }, name(q)),
          el("span", { class: "bar" }, el("span", { class: "fill", style: `width:${pct}%;background:${PCOL[q]}` })),
          el("span", { class: "bar-pct" }, `${pct}%`),
        ),
      );
    });
  }

  function renderHand() {
    const me = st.players[board.human];
    const box = $("hand");
    box.textContent = "";
    me.hand.forEach((n, r) => {
      box.append(
        el("span", { class: "res r" + r + (n ? "" : " zero") }, el("span", { "aria-hidden": "true" }, RES_ICON[r]), ` ${T.res[r]} `, el("b", {}, String(n))),
      );
    });
    const dv = $("devs");
    dv.textContent = "";
    me.dev.forEach((n, c) => {
      if (!n) return;
      const fresh = me.dev_new[c];
      dv.append(el("span", { class: "devcard" }, `${T.dev[c]} ×${n}`, fresh ? el("small", {}, " " + T.newCard) : null));
    });
  }

  function button(label, onclick, opts) {
    const b = el("button", { type: "button", class: (opts && opts.cls) || "" }, label);
    b.addEventListener("click", onclick);
    if (opts && opts.disabled) b.disabled = true;
    if (opts && opts.hint) b.classList.add("hint");
    return b;
  }

  function renderActions(aiTurn) {
    const box = $("actions");
    box.textContent = "";
    const status = $("status");
    if (st.phase === "over") {
      status.textContent = st.winner === board.human ? T.youWin : T.winner(name(st.winner));
      return;
    }
    if (aiTurn || st.to_act !== board.human) {
      return;
    }
    const ph = T.phase[st.phase];
    status.textContent =
      T.yourTurn + ": " + (typeof ph === "function" ? ph(st.phase === "discard" ? st.discard_left : st.free_roads) : ph);
    const isHint = (a) => sameAct(a, hintAct);

    if (pending) {
      box.append(
        el(
          "div",
          { class: "row" },
          button(T.buildHere[pending[0]] || T.confirm, () => act(pending), { cls: "primary" }),
          button(T.cancel, () => {
            pending = null;
            render();
          }),
        ),
      );
    }
    if (st.phase === "pre_roll") {
      box.append(button(T.roll, () => act(["roll"]), { cls: "primary", hint: isHint(["roll"]) }));
      if (has("knight")) box.append(button(`${T.dev[0]} ${T.play}`, () => act(["knight"]), { hint: isHint(["knight"]) }));
    } else if (st.phase === "discard") {
      const row = el("div", { class: "row" });
      for (const a of legal()) row.append(button(`${RES_ICON[a[1]]} ${T.res[a[1]]}`, () => act(a), { hint: isHint(a) }));
      box.append(row);
    } else if (st.phase === "steal") {
      const row = el("div", { class: "row" });
      for (const a of legal()) row.append(button(name(a[1]), () => act(a), { hint: isHint(a) }));
      box.append(row);
    } else if (st.phase === "main") {
      renderMain(box, isHint);
    }
    if (st.phase !== "setup_road") {
      box.append(button(T.hint, showHint, { cls: "ghost" }));
    }
  }

  function renderMain(box, isHint) {
    const row = el("div", { class: "row" });
    if (has("buy_dev")) row.append(button(T.buyDev, () => act(["buy_dev"]), { hint: isHint(["buy_dev"]) }));
    if (has("trade"))
      row.append(
        button(T.trade, () => {
          mode = mode === "trade" ? null : "trade";
          tradeGive = null;
          render();
        }, { hint: hintAct && hintAct[0] === "trade" }),
      );
    if (has("knight")) row.append(button(`${T.dev[0]} ${T.play}`, () => act(["knight"]), { hint: isHint(["knight"]) }));
    if (has("road_building"))
      row.append(button(`${T.dev[2]} ${T.play}`, () => act(["road_building"]), { hint: isHint(["road_building"]) }));
    if (has("plenty"))
      row.append(
        button(`${T.dev[3]} ${T.play}`, () => {
          mode = "plenty";
          plentyPick = [];
          render();
        }, { hint: hintAct && hintAct[0] === "plenty" }),
      );
    if (has("monopoly"))
      row.append(
        button(`${T.dev[4]} ${T.play}`, () => {
          mode = "monopoly";
          render();
        }, { hint: hintAct && hintAct[0] === "monopoly" }),
      );
    row.append(button(T.end, () => act(["end"]), { cls: "primary", hint: isHint(["end"]) }));
    box.append(row);

    if (mode === "trade") {
      const gives = [...new Set(legal().filter((a) => a[0] === "trade").map((a) => a[1]))];
      const r1 = el("div", { class: "row" }, el("span", { class: "lbl" }, T.give));
      for (const g of gives)
        r1.append(
          button(`${RES_ICON[g]} ${T.res[g]} ${st.ratios[g]}`, () => {
            tradeGive = g;
            render();
          }, { cls: tradeGive === g ? "on" : "" }),
        );
      box.append(r1);
      if (tradeGive != null) {
        const r2 = el("div", { class: "row" }, el("span", { class: "lbl" }, T.get));
        for (const a of legal().filter((x) => x[0] === "trade" && x[1] === tradeGive))
          r2.append(button(`${RES_ICON[a[2]]} ${T.res[a[2]]}`, () => act(a), { hint: isHint(a) }));
        box.append(r2);
      }
    } else if (mode === "plenty") {
      const r = el("div", { class: "row" }, el("span", { class: "lbl" }, T.pickTwo));
      for (let k = 0; k < 5; k++)
        r.append(
          button(`${RES_ICON[k]} ${T.res[k]}${plentyPick.filter((x) => x === k).length ? " ✓" : ""}`, () => {
            plentyPick.push(k);
            if (plentyPick.length === 2) {
              const [a, b] = plentyPick.slice().sort();
              const m = ["plenty", a, b];
              if (legal().some((x) => sameAct(x, m))) return act(m);
              plentyPick = [];
            }
            render();
          }),
        );
      box.append(r);
    } else if (mode === "monopoly") {
      const r = el("div", { class: "row" }, el("span", { class: "lbl" }, T.pickOne));
      for (const a of legal().filter((x) => x[0] === "monopoly"))
        r.append(button(`${RES_ICON[a[1]]} ${T.res[a[1]]}`, () => act(a), { hint: isHint(a) }));
      box.append(r);
    }
  }

  async function showHint() {
    if (busy) return;
    const out = $("hint-out");
    out.textContent = T.hintWait;
    busy = true;
    let h = null;
    try {
      h = await call("hint", null);
    } finally {
      busy = false;
    }
    if (!h) {
      out.textContent = "";
      return;
    }
    hintAct = h.action;
    const a = h.action;
    out.textContent = `${T.hintIs}: ${hintText(a)}`;
    render();
  }

  // おすすめの手を「これから打つ手」の言い方で
  function hintText(a) {
    const H = T.hintAct;
    switch (a[0]) {
      case "roll":
        return T.roll;
      case "end":
        return T.end;
      case "buy_dev":
        return T.buyDev;
      case "knight":
      case "road_building":
        return `${T.dev[a[0] === "knight" ? 0 : 2]} ${T.play}`;
      case "plenty":
        return `${T.dev[3]} ${T.play} (${T.res[a[1]]}, ${T.res[a[2]]})`;
      case "monopoly":
        return `${T.dev[4]} ${T.play} (${T.res[a[1]]})`;
      case "steal":
        return H.steal(name(a[1]));
      case "discard":
        return H.discard(T.res[a[1]]);
      case "trade":
        return H.trade(T.res[a[1]], st.ratios[a[1]], T.res[a[2]]);
      default:
        return (T.buildHere[a[0]] || a[0]) + " " + H.mark;
    }
  }

  function renderLog() {
    const box = $("log");
    box.textContent = "";
    for (const it of logItems.slice(-40).reverse()) {
      box.append(
        el("li", { class: it.roll7 ? "seven" : "" }, el("span", { class: "dot", style: `background:${PCOL[it.who]}` }), `${name(it.who)}: ${it.text}`),
      );
    }
  }

  function renderOver() {
    const box = $("over");
    box.hidden = false;
    box.textContent = "";
    box.append(el("h2", {}, st.winner === board.human ? T.youWin : T.winner(name(st.winner))));
    const tbl = el("table", {});
    const head = el("tr", {}, el("th", {}, ""));
    T.bd.forEach((b) => head.append(el("th", {}, b)));
    tbl.append(head);
    st.players.forEach((p, q) => {
      const row = el("tr", {}, el("th", {}, el("span", { class: "dot", style: `background:${PCOL[q]}` }), name(q)));
      const vals = [
        p.settlements,
        p.cities * 2,
        st.longest === q ? 2 : 0,
        st.army === q ? 2 : 0,
        p.vp_cards || 0,
        p.vp,
      ];
      vals.forEach((v) => row.append(el("td", {}, String(v))));
      tbl.append(row);
    });
    box.append(el("p", { class: "lbl" }, T.breakdown), el("div", { class: "scroll" }, tbl));
    box.append(button(T.again, () => newGame(), { cls: "primary" }));
  }

  // ---- 始める ----
  async function newGame() {
    $("over").hidden = true;
    $("setup").hidden = true;
    $("game").hidden = false;
    logItems.length = 0;
    pending = mode = hintAct = null;
    $("hint-out").textContent = "";
    const level = $("level").value;
    const seatSel = $("seat").value;
    const human = seatSel === "random" ? Math.floor(Math.random() * 4) : Number(seatSel);
    $("status").textContent = T.loading;
    busy = true;
    let r;
    try {
      r = await call("new", { human, level });
    } catch (e) {
      $("status").textContent = T.loadFail;
      console.error(e);
      return;
    }
    board = r.board;
    st = r.state;
    busy = false;
    drawBoard();
    render();
    runAI();
  }

  function init() {
    startWorker();
    call("state", null).catch(() => {}); // 先に Python を読み込み始める
    $("start").addEventListener("click", newGame);
    $("restart").addEventListener("click", () => {
      $("setup").hidden = false;
      $("game").hidden = true;
      $("over").hidden = true;
    });
  }
  init();
})();
