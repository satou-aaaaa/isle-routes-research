// 公開ページ（docs/*.html と docs/en/*.html）の UI 点検。スマホ幅とPC幅で開き、機械で分かる問題を探す。
//
//   node scripts/ui_check.mjs                 # 点検だけ（問題があれば終了コード 1）
//   node scripts/ui_check.mjs --shots DIR     # 各ページ・各幅のスクリーンショットも DIR に保存
//   node scripts/ui_check.mjs play.html       # 指定したページだけ
//
// 見ること: コンソールのエラー・読み込み失敗、横のはみ出し、押す場所の大きさ（24px 未満は ✗、
// スマホで高さ 44px 未満は △）と名前、12px 未満の文字、言語の自動切り替え。
// 対戦ページは対局を始め、初期配置の村と道を盤の上で選んで確定し、サイコロのあとの手番を2回終える
// （1回目は「AIならどう打つ？」も押す）。クイズは選択肢と盤の印で1問ずつ答え、結果の欄を見る。
// 点検の部分は姉妹プロジェクト carcassonne-research の scripts/ui_check.mjs から写している。
//
// Pyodide は cdn.jsdelivr.net から読む。そこへ届かない環境では、npm の pyodide パッケージを
// 展開したフォルダを PYODIDE_DIR に渡すと、そこから読ませる（npm pack pyodide@0.26.4 → package/）。

import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const DOCS = path.join(ROOT, "docs");

function loadPlaywright() {
  const require = createRequire(import.meta.url);
  const tries = [
    "playwright",
    path.join(process.env.npm_config_prefix || "/opt/node22", "lib/node_modules/playwright"),
  ];
  try {
    const g = require("child_process").execSync("npm root -g", { encoding: "utf8" }).trim();
    tries.push(path.join(g, "playwright"));
  } catch {}
  for (const t of tries) {
    try {
      return require(t);
    } catch {}
  }
  console.error("playwright が見つかりません（npm i -g playwright）");
  process.exit(2);
}

const VIEWPORTS = [
  { name: "mobile", width: 390, height: 844, isMobile: true, hasTouch: true },
  { name: "pc", width: 1280, height: 800, isMobile: false, hasTouch: false },
];

const TYPES = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".css": "text/css",
};

function serve() {
  const server = http.createServer((req, res) => {
    const p = decodeURIComponent(new URL(req.url, "http://x").pathname);
    const f = path.join(DOCS, p === "/" ? "index.html" : p);
    if (!f.startsWith(DOCS) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) {
      res.writeHead(404).end();
      return;
    }
    res.writeHead(200, { "content-type": TYPES[path.extname(f)] || "application/octet-stream" });
    fs.createReadStream(f).pipe(res);
  });
  return new Promise((ok) => server.listen(0, "127.0.0.1", () => ok(server)));
}

// ページ内で実行する点検。結果は { errors: [], warns: [] }
function inspect(isMobile) {
  const errors = [];
  const warns = [];
  const vw = document.documentElement.clientWidth;
  const desc = (el) => {
    let s = el.tagName.toLowerCase();
    if (el.id) s += "#" + el.id;
    else if (el.className && typeof el.className === "string")
      s += "." + el.className.trim().split(/\s+/).join(".");
    const t = (el.getAttribute("aria-label") || el.textContent || "").trim().slice(0, 20);
    return t ? `${s}「${t}」` : s;
  };
  const visible = (el) => {
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && cs.visibility !== "hidden" && cs.display !== "none";
  };

  if (!document.querySelector('meta[name="viewport"]')) errors.push("viewport の指定がない");
  if (!document.title.trim()) errors.push("title が空");

  // 横のはみ出し
  const sw = document.scrollingElement.scrollWidth;
  if (sw > vw + 1) {
    const culprits = [];
    for (const el of document.body.querySelectorAll("*")) {
      if (!visible(el)) continue;
      const r = el.getBoundingClientRect();
      if (r.right > vw + 1 && culprits.length < 5) {
        // 横スクロールできる箱の中身は対象外
        let p = el.parentElement;
        let scrolls = false;
        while (p && p !== document.body) {
          const ox = getComputedStyle(p).overflowX;
          if (ox === "auto" || ox === "scroll" || ox === "hidden") scrolls = true;
          p = p.parentElement;
        }
        if (!scrolls) culprits.push(`${desc(el)} 右端${Math.round(r.right)}px`);
      }
    }
    errors.push(`横にはみ出す（ページ幅${sw}px > 画面${vw}px）: ${culprits.join(" / ")}`);
  }

  // 横スクロールの箱（表など）。中身が切れて見えるので、スマホでは避けたい
  const scrollers = [];
  for (const el of document.body.querySelectorAll("*")) {
    if (!visible(el)) continue;
    const ox = getComputedStyle(el).overflowX;
    if ((ox === "auto" || ox === "scroll") && el.scrollWidth > el.clientWidth + 1)
      scrollers.push(`${desc(el)} 中身${el.scrollWidth}px/幅${el.clientWidth}px`);
  }
  if (scrollers.length) warns.push(`横スクロールしないと見えない箱: ${scrollers.slice(0, 4).join(" / ")}`);

  // 押せるもの: 大きさと名前
  const controls = document.querySelectorAll(
    "button, input:not([type=hidden]), select, textarea, nav a, a.btn, [role=button], summary",
  );
  const small = [];
  const smallWarn = [];
  for (const el of controls) {
    if (!visible(el)) continue;
    const r = el.getBoundingClientRect();
    // チェックボックスは label ごと押せるので label の大きさで見る
    let box = r;
    const lab = el.closest("label") || (el.id && document.querySelector(`label[for="${el.id}"]`));
    if ((el.type === "checkbox" || el.type === "radio") && lab) box = lab.getBoundingClientRect();
    if (box.width < 24 - 0.5 || box.height < 24 - 0.5)
      small.push(`${desc(el)} ${Math.round(box.width)}×${Math.round(box.height)}`);
    else if (isMobile && box.height < 44 - 0.5)
      smallWarn.push(`${desc(el)} 高さ${Math.round(box.height)}`);
    const name =
      el.getAttribute("aria-label") ||
      el.getAttribute("title") ||
      (el.labels && [...el.labels].map((l) => l.textContent).join("")) ||
      el.textContent ||
      el.value ||
      el.getAttribute("placeholder");
    if (!name || !String(name).trim()) errors.push(`名前のない操作部品: ${desc(el)}`);
  }
  if (small.length) errors.push(`押す場所が 24px 未満: ${small.slice(0, 8).join(" / ")}`);
  if (smallWarn.length)
    warns.push(`スマホで高さ 44px 未満が ${smallWarn.length} 個（例: ${smallWarn.slice(0, 4).join(" / ")}）`);

  for (const img of document.querySelectorAll("img")) {
    if (!img.hasAttribute("alt")) errors.push(`alt のない画像: ${img.src.slice(-40)}`);
  }

  // 小さすぎる文字（本文の文字を持つ要素だけ）
  const tiny = new Set();
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const n = walker.currentNode;
    if (!n.textContent.trim()) continue;
    const el = n.parentElement;
    if (!el || !visible(el) || el.closest("svg, kbd")) continue;
    const fs = parseFloat(getComputedStyle(el).fontSize);
    if (fs < 12) tiny.add(`${desc(el)} ${fs}px`);
  }
  if (tiny.size) warns.push(`12px 未満の文字が ${tiny.size} か所（例: ${[...tiny].slice(0, 3).join(" / ")}）`);

  return { errors, warns };
}

const PYODIDE_URL = "https://cdn.jsdelivr.net/pyodide/v0.26.4/full/";

async function routePyodide(ctx) {
  const dir = process.env.PYODIDE_DIR;
  if (!dir) return;
  await ctx.route(PYODIDE_URL + "**", (route) => {
    const name = route.request().url().slice(PYODIDE_URL.length).split("?")[0];
    const f = path.join(dir, name);
    if (!fs.existsSync(f)) return route.fulfill({ status: 404, body: "" });
    const type = name.endsWith(".wasm")
      ? "application/wasm"
      : name.endsWith(".js")
        ? "text/javascript"
        : name.endsWith(".json")
          ? "application/json"
          : "application/octet-stream";
    return route.fulfill({
      status: 200,
      body: fs.readFileSync(f),
      headers: { "content-type": type, "access-control-allow-origin": "*" },
    });
  });
}

// 対戦ページ: 対局を始め、人の手を盤とボタンで打ちながら、サイコロのあとの手番を2回終えるまで進める
async function exercisePlay(page, shotDir, stem, problems) {
  await page.click("#start");
  const humanTurn = () =>
    page.waitForFunction(
      () => {
        const s = document.getElementById("status").textContent;
        return document.querySelector("#actions button, #board .target") && !/考えて|thinking/.test(s);
      },
      null,
      { timeout: 120000 },
    );
  const labelsOf = async () => {
    const btns = await page.$$("#actions button");
    return [btns, await Promise.all(btns.map((b) => b.textContent()))];
  };
  let mainTurns = 0;
  let picked = false;
  for (let step = 0; step < 80 && mainTurns < 2; step++) {
    await humanTurn();
    const status = await page.textContent("#status");
    const target = await page.$("#board .target");
    let [btns, labels] = await labelsOf();
    const end = labels.findIndex((t) => /手番を終える|End turn/.test(t));
    const roll = labels.findIndex((t) => /サイコロを振る|Roll the dice/.test(t));
    if (end >= 0) {
      mainTurns++;
      if (mainTurns === 1) {
        const h = labels.findIndex((t) => /AIならどう打つ|What would the AI do/.test(t));
        if (h < 0) problems.push("対戦ページ: 手番の中に「AIならどう打つ？」がない");
        else {
          await btns[h].click();
          await page.waitForFunction(
            () => /おすすめ|suggests/.test(document.getElementById("hint-out").textContent),
            null,
            { timeout: 90000 },
          );
          if (shotDir) await page.screenshot({ path: path.join(shotDir, `${stem}_hint.png`), fullPage: true });
        }
        [btns, labels] = await labelsOf();
      }
      await btns[labels.findIndex((t) => /手番を終える|End turn/.test(t))].click();
    } else if (roll >= 0) {
      await btns[roll].click();
    } else if (target) {
      await target.click();
      const ok = await page.waitForSelector("#actions button.primary", { timeout: 5000 });
      if (shotDir && !picked) await page.screenshot({ path: path.join(shotDir, `${stem}_pick.png`) });
      picked = true;
      await ok.click();
    } else if (btns.length) {
      await btns[0].click();
    } else {
      problems.push(`対戦ページ: 打てる手が見つからない（${status}）`);
      return false;
    }
    await page.waitForTimeout(50);
  }
  return mainTurns >= 2;
}

async function main() {
  const args = process.argv.slice(2);
  const shotDir = args.includes("--shots") ? args[args.indexOf("--shots") + 1] : null;
  if (shotDir) fs.mkdirSync(shotDir, { recursive: true });
  const only = args.filter((a) => a.endsWith(".html"));
  const pages = only.length
    ? only
    : [
        ...fs.readdirSync(DOCS).filter((f) => f.endsWith(".html")).sort(),
        ...fs
          .readdirSync(path.join(DOCS, "en"))
          .filter((f) => f.endsWith(".html"))
          .sort()
          .map((f) => "en/" + f),
      ];
  const { chromium } = loadPlaywright();
  const browser = await chromium.launch();
  const server = await serve();
  const base = `http://127.0.0.1:${server.address().port}/`;
  let failed = 0;

  // 言語の自動切り替え（初めて来た人）
  for (const [locale, from, to] of [
    ["en-US", "", "en/index.html"],
    ["ja-JP", "en/play.html", "play.html"],
    ["ja-JP", "index.html", "index.html"],
  ]) {
    const ctx = await browser.newContext({ locale });
    const page = await ctx.newPage();
    await page.goto(base + from, { waitUntil: "load" });
    await page.waitForLoadState("load");
    const got = page.url().replace(base, "");
    const ok = got === to;
    console.log(`${ok ? "✓" : "✗"} 言語の自動切り替え ${locale} ${from || "/"} → ${got || "/"}`);
    if (!ok) failed++;
    await ctx.close();
  }

  for (const vp of VIEWPORTS) {
    for (const file of pages) {
      const ctx = await browser.newContext({
        viewport: { width: vp.width, height: vp.height },
        isMobile: vp.isMobile,
        hasTouch: vp.hasTouch,
        deviceScaleFactor: 1,
        locale: file.startsWith("en/") ? "en-US" : "ja-JP",
      });
      await routePyodide(ctx);
      const page = await ctx.newPage();
      const problems = [];
      page.on("console", (m) => {
        if (m.type() === "error") problems.push(`コンソールエラー: ${m.text().slice(0, 160)}`);
      });
      page.on("pageerror", (e) => problems.push(`スクリプトエラー: ${String(e).slice(0, 160)}`));
      page.on("response", (r) => {
        if (r.status() >= 400) problems.push(`読み込み失敗 ${r.status()}: ${r.url().replace(base, "")}`);
      });
      await page.goto(base + file, { waitUntil: "load" });
      await page.waitForTimeout(300);
      let res = await page.evaluate(inspect, vp.isMobile);
      const stem = file.replace(".html", "").replace("/", "_") + "_" + vp.name;
      if (shotDir) await page.screenshot({ path: path.join(shotDir, `${stem}.png`), fullPage: true });
      if (page.url() !== base + file) problems.push(`別のページに移された: ${page.url().replace(base, "")}`);
      if (file.endsWith("play.html")) {
        try {
          const ok = await exercisePlay(page, shotDir, stem, problems);
          if (!ok) problems.push("対戦ページ: サイコロのあとの手番まで進められない");
          const r2 = await page.evaluate(inspect, vp.isMobile);
          res = { errors: [...res.errors, ...r2.errors], warns: [...res.warns, ...r2.warns] };
          if (shotDir) await page.screenshot({ path: path.join(shotDir, `${stem}_ingame.png`), fullPage: true });
        } catch (e) {
          problems.push(`対戦ページの操作に失敗: ${String(e).slice(0, 200)}`);
          if (shotDir) await page.screenshot({ path: path.join(shotDir, `${stem}_fail.png`), fullPage: true });
        }
      }
      if (file.endsWith("quiz.html")) {
        // クイズ: 1問答えると、正解・各選択肢の勝率・学び・次の問題が出る
        try {
          await page.click("#qchoices .opt");
          await page.waitForSelector("#qresult:not([hidden]) .lesson", { timeout: 5000 });
          const rates = await page.$$eval("#qchoices .opt em", (es) => es.length);
          if (rates !== 4) problems.push(`クイズ: 答えたあとの勝率が ${rates} 個（4個のはず）`);
          await page.click("#qresult button.primary");
          await page.waitForSelector("#qresult[hidden]", { state: "attached", timeout: 5000 });
          await page.click("#qboard .choice");
          await page.waitForSelector("#qresult:not([hidden])", { timeout: 5000 });
          const r2 = await page.evaluate(inspect, vp.isMobile);
          res = { errors: [...res.errors, ...r2.errors], warns: [...res.warns, ...r2.warns] };
          if (shotDir) await page.screenshot({ path: path.join(shotDir, `${stem}_answered.png`), fullPage: true });
        } catch (e) {
          problems.push(`クイズの操作に失敗: ${String(e).slice(0, 200)}`);
        }
      }
      const errs = [...problems, ...res.errors];
      console.log(`${errs.length ? "✗" : "✓"} ${file} (${vp.name})`);
      for (const e of errs) console.log("   ✗ " + e);
      for (const w of res.warns) console.log("   △ " + w);
      if (errs.length) failed++;
      await ctx.close();
    }
  }
  await browser.close();
  server.close();
  if (failed) {
    console.log(`\n✗ ${failed} 件の問題`);
    process.exit(1);
  }
  console.log("\nすべて通りました");
}

main();
