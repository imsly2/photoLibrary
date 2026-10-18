// Headless Edge over CDP: open pictures that have no preview yet, measure and screenshot the viewer.
import { spawn } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";

const [, , outArg, base = "http://127.0.0.1:8816"] = process.argv;
const outDir = resolve(outArg);
mkdirSync(outDir, { recursive: true });
const PORT = 9333;
const EDGE = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
const edge = spawn(EDGE, ["--headless=new", `--remote-debugging-port=${PORT}`, `--user-data-dir=${join(outDir, "edge-profile")}`,
  "--window-size=1400,900", "--no-first-run", "about:blank"], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

let target;
for (let i = 0; i < 150 && !target; i++) {
  await sleep(200);
  try { target = (await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json()).find((t) => t.type === "page"); } catch {}
}
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener("open", r));
let seq = 0;
const pending = new Map();
ws.addEventListener("message", (m) => { const d = JSON.parse(m.data); if (pending.has(d.id)) { pending.get(d.id)(d); pending.delete(d.id); } });
const cdp = (method, params = {}) => new Promise((r) => { const id = ++seq; pending.set(id, r); ws.send(JSON.stringify({ id, method, params })); });
const js = async (expr) => (await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true })).result?.result?.value;
const shot = async (name) => { const d = await cdp("Page.captureScreenshot", { format: "png" }); writeFileSync(join(outDir, name), Buffer.from(d.result.data, "base64")); return name; };
const post = (path, body) => fetch(base + path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

await cdp("Emulation.setDeviceMetricsOverride", { width: 1400, height: 900, deviceScaleFactor: 1, mobile: false });
await cdp("Page.navigate", { url: base + "/" });
for (let i = 0; i < 100 && (await js("document.querySelectorAll('.cell[data-filename]').length")) < 3; i++) await sleep(200);

const MEASURE = `(() => {
  const stage = document.getElementById("viewer-stage").getBoundingClientRect();
  const layer = (id) => { const el = document.getElementById(id); const r = el.getBoundingClientRect();
    return { hidden: el.hidden, loaded: !!(el.complete && el.naturalWidth), which: el.getAttribute("data-which"),
      x: Math.round(r.left - stage.left), y: Math.round(r.top - stage.top), w: Math.round(r.width), h: Math.round(r.height) }; };
  const ph = document.getElementById("viewer-placeholder");
  return { stage: { w: Math.round(stage.width), h: Math.round(stage.height) }, original: layer("viewer-original"),
    preview: layer("viewer-image"), placeholder: ph.hidden ? null : ph.textContent };
})()`;
const fitted = (layer, stage, aspect) => {
  const ratio = layer.w / layer.h;
  const centered = Math.abs(layer.x + layer.w / 2 - stage.w / 2) <= 2 && Math.abs(layer.y + layer.h / 2 - stage.h / 2) <= 2;
  const inside = layer.x >= -1 && layer.y >= -1 && layer.x + layer.w <= stage.w + 1 && layer.y + layer.h <= stage.h + 1;
  const touches = Math.abs(layer.w - stage.w) <= 2 || Math.abs(layer.h - stage.h) <= 2;
  return { aspect: +ratio.toFixed(3), expected: aspect, aspectOk: Math.abs(ratio - aspect) < 0.01, centered, inside, touches };
};

const PICS = [["IMG_0023.JPG", 2592 / 1936], ["IMG_0240.JPG", 1936 / 2592], ["IMG_2518.JPG", 2448 / 3264]];
const result = { noPreview: [], previewArrives: null };
const open = async (file) => {
  await js(`document.querySelector('.cell[data-filename="${file}"]').click()`);
  await sleep(1500);
};
const close = () => js(`document.getElementById("viewer-back").click()`);

for (const [file, aspect] of PICS) {
  await open(file);
  const m = await js(MEASURE);
  result.noPreview.push({ file, ...m, check: fitted(m.original, m.stage, +aspect.toFixed(3)), screenshot: await shot(`no-preview-${file}.png`) });
  await close();
  await sleep(300);
}

await open("IMG_0240.JPG");
const before = await js(MEASURE);
await post("/api/jobs", { action: "resume" });
let ready = false;
for (let i = 0; i < 60 && !ready; i++) {
  await sleep(500);
  ready = !!(await js("(() => { const el = document.getElementById('viewer-image'); return !el.hidden && el.complete && el.naturalWidth > 0 && el.getAttribute('data-which') === 'preview'; })()"));
}
await sleep(500);
const after = await js(MEASURE);
const same = (a, b) => Math.abs(a.x - b.x) <= 1 && Math.abs(a.y - b.y) <= 1 && Math.abs(a.w - b.w) <= 1 && Math.abs(a.h - b.h) <= 1;
result.previewArrives = { file: "IMG_0240.JPG", before, after, previewShown: ready,
  previewSameBoxAsOriginalBefore: same(before.original, after.preview), originalDidNotMove: same(before.original, after.original),
  screenshot: await shot("preview-arrived-IMG_0240.JPG.png") };

const ok = result.noPreview.every((r) => r.check.aspectOk && r.check.centered && r.check.inside && r.check.touches && !r.original.hidden)
  && result.previewArrives.previewShown && result.previewArrives.previewSameBoxAsOriginalBefore && result.previewArrives.originalDidNotMove;
result.pass = ok;
writeFileSync(join(outDir, "result.json"), JSON.stringify(result, null, 2) + "\n");
console.log(JSON.stringify(result, null, 2));
ws.close();
edge.kill();
process.exit(ok ? 0 : 1);
