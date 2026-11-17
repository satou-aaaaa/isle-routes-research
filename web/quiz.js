// 初期配置クイズ（docs/quiz.html と docs/en/quiz.html で共通）。問題は quiz_data.js（window.QUIZ）。
(function () {
  "use strict";
  const LANG = document.documentElement.lang === "en" ? "en" : "ja";
  const T = {
    ja: {
      res: ["木材", "れんが", "羊毛", "小麦", "鉱石"],
      q: (n, total) => `第${n}問 / 全${total}問`,
      who: ["1番手", "2番手", "3番手", "4番手"],
      ask: (seat, nth) => `あなたは${seat}。${nth}の村をどこに置きますか？`,
      nth: ["1つ目", "2つ目"],
      right: "正解！",
      wrong: (x) => `残念。正解は ${x} です。`,
      rate: "勝率",
      dots: "点",
      port: "港",
      noPort: "港なし",
      next: "次の問題",
      again: "もう一度はじめから",
      score: (a, b) => `${b}問中 ${a}問 正解`,
      method: (n) => `勝率は、そこに置いてから最後までAIどうしで${n}局打った結果です（どの候補も同じサイコロの並びで比べています）。`,
      lessonK: "学び",
      mine: "あなたの村",
      others: "ほかの人",
      choose: "A〜D から選んでください",
    },
    en: {
      res: ["Wood", "Brick", "Wool", "Grain", "Ore"],
      q: (n, total) => `Question ${n} of ${total}`,
      who: ["1st", "2nd", "3rd", "4th"],
      ask: (seat, nth) => `You are the ${seat} seat. Where do you place your ${nth} village?`,
      nth: ["first", "second"],
      right: "Correct!",
      wrong: (x) => `Not quite. The answer is ${x}.`,
      rate: "Win rate",
      dots: "dots",
      port: "Harbor",
      noPort: "No harbor",
      next: "Next question",
      again: "Start over",
      score: (a, b) => `${a} of ${b} correct`,
      method: (n) => `Win rates come from ${n} AI-vs-AI games played to the end after placing there (every choice was compared with the same dice sequences).`,
      lessonK: "Takeaway",
      mine: "Your village",
      others: "Other players",
      choose: "Pick A–D",
    },
  }[LANG];
  const TERRAIN = ["#3f7d3a", "#b5562d", "#9fd06a", "#e7c24a", "#8b919b"];
  const DESERT = "#dcc9a0";
  const PCOL = ["#d64545", "#2f6fb5", "#8a4fbf", "#e08a12"];
  const RES_ICON = ["🌲", "🧱", "🐑", "🌾", "⛰️"];
  const LETTERS = ["A", "B", "C", "D"];
  const Q = window.QUIZ;
  const G = Q.geo;
  const SVG = "http://www.w3.org/2000/svg";
  const sv = (tag, attrs) => {
    const n = document.createElementNS(SVG, tag);
    for (const k in attrs) n.setAttribute(k, attrs[k]);
    return n;
  };
  const $ = (id) => document.getElementById(id);
  let idx = 0;
  let correct = 0;
  let answered = false;

  function hexPoints(x, y, s) {
    const pts = [];
    for (let k = 0; k < 6; k++) {
      const a = ((60 * k - 30) * Math.PI) / 180;
      pts.push(`${(x + s * Math.cos(a)).toFixed(3)},${(y + s * Math.sin(a)).toFixed(3)}`);
    }
    return pts.join(" ");
  }

  function portLabel(kind) {
    return kind === 5 ? "3:1" : `2:1 ${T.res[kind]}`;
  }

  function draw(p) {
    const svg = $("qboard");
    svg.textContent = "";
    svg.append(sv("rect", { x: -6.4, y: -5.6, width: 12.8, height: 11.2, rx: 0.6, class: "sea" }));
    p.layout.ports.forEach((kind, i) => {
      const [a, b] = G.edges[G.port_edges[i]].map((v) => G.vertices[v]);
      const mx = (a[0] + b[0]) / 2;
      const my = (a[1] + b[1]) / 2;
      const len = Math.hypot(mx, my);
      const px = mx + (mx / len) * 0.75;
      const py = my + (my / len) * 0.75;
      svg.append(sv("line", { x1: a[0], y1: a[1], x2: px, y2: py, class: "pier" }));
      svg.append(sv("line", { x1: b[0], y1: b[1], x2: px, y2: py, class: "pier" }));
      svg.append(sv("circle", { cx: px, cy: py, r: 0.42, class: "port", fill: kind === 5 ? "#fff" : TERRAIN[kind] }));
      const t = sv("text", { x: px, y: py + (kind === 5 ? 0.09 : 0.25), class: "port-t" + (kind === 5 || kind === 2 || kind === 3 ? " dark" : "") });
      t.textContent = kind === 5 ? "3:1" : "2:1";
      svg.append(t);
      if (kind !== 5) {
        const ic = sv("text", { x: px, y: py - 0.13, class: "port-i" });
        ic.textContent = RES_ICON[kind];
        svg.append(ic);
      }
    });
    G.hexes.forEach(([x, y], h) => {
      const t = p.layout.terrain[h];
      const n = p.layout.number[h];
      svg.append(sv("polygon", { points: hexPoints(x, y, 0.98), fill: t < 0 ? DESERT : TERRAIN[t] }));
      if (t >= 0) {
        const ic = sv("text", { x, y: y - 0.38, class: "hex-icon" });
        ic.textContent = RES_ICON[t];
        svg.append(ic);
      }
      if (n) {
        const hot = n === 6 || n === 8 ? " hot" : "";
        svg.append(sv("circle", { cx: x, cy: y + 0.12, r: 0.36, class: "chip" }));
        const tx = sv("text", { x, y: y + 0.25, class: "num" + hot });
        tx.textContent = n;
        svg.append(tx);
        const d = sv("text", { x, y: y + 0.43, class: "pips" + hot });
        d.textContent = "•".repeat(6 - Math.abs(7 - n));
        svg.append(d);
      }
    });
    p.road.forEach((q, e) => {
      if (q < 0) return;
      const [a, b] = G.edges[e].map((v) => G.vertices[v]);
      svg.append(sv("line", { x1: a[0], y1: a[1], x2: b[0], y2: b[1], class: "road", stroke: PCOL[q] }));
    });
    p.building.forEach((q, v) => {
      if (q < 0) return;
      const [x, y] = G.vertices[v];
      svg.append(sv("circle", { cx: x, cy: y, r: 0.2, fill: PCOL[q], class: "bld" + (q === p.me ? " mine" : "") }));
    });
    p.choices.forEach((c, i) => {
      const [x, y] = G.vertices[c.v];
      const g = sv("g", { class: "choice", "data-i": i, tabindex: 0, role: "button", "aria-label": LETTERS[i] });
      g.append(sv("circle", { cx: x, cy: y, r: 0.47 }));
      const t = sv("text", { x, y: y + 0.15 });
      t.textContent = LETTERS[i];
      g.append(t);
      g.addEventListener("click", () => answer(i));
      g.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          answer(i);
        }
      });
      svg.append(g);
    });
  }

  function lands(c) {
    return c.lands.map((l) => `${RES_ICON[l.res]}${T.res[l.res]} ${l.num}`).join(" · ");
  }

  function show() {
    const p = Q.puzzles[idx];
    answered = false;
    $("qno").textContent = T.q(idx + 1, Q.puzzles.length);
    const nth = p.step >= 4 ? T.nth[1] : T.nth[0];
    $("qask").textContent = T.ask(T.who[p.me], nth);
    $("qlegend").innerHTML =
      `<span class="dot" style="background:${PCOL[p.me]}"></span>${T.mine} · ` +
      [0, 1, 2, 3].filter((q) => q !== p.me).map((q) => `<span class="dot" style="background:${PCOL[q]}"></span>`).join("") +
      T.others;
    draw(p);
    const box = $("qchoices");
    box.textContent = "";
    p.choices.forEach((c, i) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "opt";
      b.innerHTML = `<b>${LETTERS[i]}</b><span>${lands(c)}</span><small>${c.pips} ${T.dots}${c.port != null ? " · " + T.port + " " + portLabel(c.port === "3:1" ? 5 : c.port) : ""}</small>`;
      b.addEventListener("click", () => answer(i));
      box.append(b);
    });
    $("qresult").hidden = true;
    $("qhint").textContent = T.choose;
  }

  function answer(i) {
    if (answered) return;
    answered = true;
    const p = Q.puzzles[idx];
    const ans = p.choices.findIndex((c) => c.v === p.answer);
    if (i === ans) correct++;
    document.querySelectorAll("#qchoices .opt").forEach((b, k) => {
      b.disabled = true;
      b.classList.add(k === ans ? "right" : k === i ? "wrong" : "dim");
      const c = p.choices[k];
      const r = document.createElement("em");
      r.textContent = `${T.rate} ${(c.rate * 100).toFixed(1)}%`;
      b.append(r);
    });
    document.querySelectorAll("#qboard .choice").forEach((g, k) => {
      g.classList.add(k === ans ? "right" : k === i ? "wrong" : "dim");
    });
    const res = $("qresult");
    res.hidden = false;
    res.innerHTML = "";
    const h = document.createElement("p");
    h.className = "verdict " + (i === ans ? "ok" : "ng");
    h.textContent = i === ans ? T.right : T.wrong(LETTERS[ans]);
    const l = document.createElement("p");
    l.className = "box lesson";
    l.innerHTML = `<span class="k">${T.lessonK}</span>`;
    l.append(p.lesson[LANG]);
    const m = document.createElement("p");
    m.className = "note";
    m.textContent = T.method(p.rollouts);
    const b = document.createElement("button");
    b.type = "button";
    b.className = "primary";
    const last = idx === Q.puzzles.length - 1;
    b.textContent = last ? T.again : T.next;
    b.addEventListener("click", () => {
      if (last) {
        idx = 0;
        correct = 0;
      } else idx++;
      show();
      $("qtop").scrollIntoView({ behavior: "smooth", block: "start" });
    });
    res.append(h, l, m);
    if (last) {
      const s = document.createElement("p");
      s.className = "score";
      s.textContent = T.score(correct, Q.puzzles.length);
      res.append(s);
    }
    res.append(b);
    $("qhint").textContent = "";
  }

  show();
})();
