// 対戦ページの裏で Python（Pyodide）を動かす。ルールと AI は研究で使う src/isle をそのまま使う。
// docs/py/ の .py は scripts/build_pages.py が src/isle から写す（手で直さない）。
/* global importScripts, loadPyodide */
importScripts("https://cdn.jsdelivr.net/pyodide/v0.26.4/full/pyodide.js");

let py = null;
let api = null;

async function boot() {
  py = await loadPyodide();
  const files = await (await fetch("py/manifest.json")).json();
  py.FS.mkdirTree("/home/pyodide/isle");
  for (const f of files) {
    const text = await (await fetch("py/isle/" + f)).text();
    py.FS.writeFile("/home/pyodide/isle/" + f, text);
  }
  py.runPython("import sys; sys.path.insert(0, '/home/pyodide')");
  api = py.pyimport("isle.webapi");
}

const ready = boot();

self.onmessage = async (e) => {
  const { id, fn, arg } = e.data;
  try {
    await ready;
    let out;
    if (fn === "new") out = api.js_new(JSON.stringify(arg || {}));
    else if (fn === "state") out = api.js_state();
    else if (fn === "act") out = api.js_act(JSON.stringify(arg));
    else if (fn === "ai") out = api.js_ai_step();
    else if (fn === "hint") out = api.js_hint();
    else throw new Error("unknown " + fn);
    self.postMessage({ id, ok: true, data: JSON.parse(out) });
  } catch (err) {
    self.postMessage({ id, ok: false, error: String(err) });
  }
};
