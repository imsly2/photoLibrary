// Time what Steve feels: first page load, filtering by person, chip filters and
// opening a picture, on a processed scratch library, idle and while the AI drain
// is busy. Headless Edge over CDP (Node 24 WebSocket), no Playwright.
//
// usage: node ui_timing.mjs <app-dir> <label> <port> <fixture-dir>
//   <fixture-dir> is the output of ui_fixture.py (pictures/ + library-data/).
//   The server runs on the fixture itself (records live in pictures/.library, so a
//   copy would need relocation). Because the "processing" phase rewrites records,
//   the catalog state is snapshotted on first use and restored before every run.
import { spawn } from "node:child_process";
import { cpSync, existsSync, mkdirSync, openSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";

const [, , appArg, label, portArg, fixtureArg] = process.argv;
const APP = resolve(appArg);
const PORT = Number(portArg);
const FIXTURE = resolve(fixtureArg);
const BASE = `http://127.0.0.1:${PORT}`;
const HERE = resolve(new URL(".", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1"));
const REPO = resolve(HERE, "../../../../../..");
const RUN = resolve(REPO, ".qa/perf-next/ui-runs", label);
const ROOT = join(FIXTURE, "library-data");
const DOT = join(FIXTURE, "pictures", ".library");
const SNAP = join(FIXTURE, "snapshot");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

mkdirSync(RUN, { recursive: true });
if (!existsSync(SNAP)) {
  cpSync(ROOT, join(SNAP, "library-data"), { recursive: true });
  cpSync(DOT, join(SNAP, ".library"), { recursive: true });
} else {
  rmSync(ROOT, { recursive: true, force: true });
  rmSync(DOT, { recursive: true, force: true });
  cpSync(join(SNAP, "library-data"), ROOT, { recursive: true });
  cpSync(join(SNAP, ".library"), DOT, { recursive: true });
}
const settings = JSON.parse(readFileSync(join(ROOT, "settings.json"), "utf-8"));
settings.port = PORT;
settings.listenHost = "127.0.0.1";
writeFileSync(join(ROOT, "settings.json"), JSON.stringify(settings, null, 2) + "\n");

const server = spawn("J:\\slyOS\\projects\\photoLibrary\\.venv\\Scripts\\python.exe", ["-m", "library", "--root", ROOT, "serve"],
  { cwd: APP, env: { ...process.env, PATH: "C:\\ffmpeg\\bin;" + process.env.PATH, PYTHONPATH: APP },
    stdio: ["ignore", openSync(join(RUN, "server.out.log"), "w"), openSync(join(RUN, "server.err.log"), "w")] });
const api = async (path, body) => {
  const t = performance.now();
  const res = await fetch(BASE + path, body === undefined ? {} :
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const json = await res.json();
  return { json, ms: +(performance.now() - t).toFixed(1) };
};
for (let i = 0; i < 150; i++) { try { await api("/api/health"); break; } catch { await sleep(200); } }
const sources = (await api("/api/sources")).json;
const sourceId = sources[0] && sources[0].id;

const CDP_PORT = 9400 + (PORT % 100);
const edge = spawn("C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe", ["--headless=new",
  `--remote-debugging-port=${CDP_PORT}`, `--user-data-dir=${join(RUN, "edge-profile")}`, "--window-size=1400,900",
  "--no-first-run", "about:blank"], { stdio: "ignore" });
let target;
for (let i = 0; i < 150 && !target; i++) {
  await sleep(200);
  try { target = (await (await fetch(`http://127.0.0.1:${CDP_PORT}/json/list`)).json()).find((t) => t.type === "page"); } catch {}
}
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener("open", r));
let seq = 0;
const pending = new Map();
const net = new Map();
const finished = [];
ws.addEventListener("message", (m) => {
  const d = JSON.parse(m.data);
  if (pending.has(d.id)) { pending.get(d.id)(d); pending.delete(d.id); }
  if (d.method === "Network.requestWillBeSent") net.set(d.params.requestId, { url: d.params.request.url, t0: d.params.timestamp });
  if (d.method === "Network.loadingFinished" && net.has(d.params.requestId)) {
    const r = net.get(d.params.requestId);
    finished.push({ url: r.url, ms: +((d.params.timestamp - r.t0) * 1000).toFixed(1), at: performance.now() });
    net.delete(d.params.requestId);
  }
});
const cdp = (method, params = {}) => new Promise((r) => { const id = ++seq; pending.set(id, r); ws.send(JSON.stringify({ id, method, params })); });
const js = async (expr) => (await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true })).result?.result?.value;
const shot = async (name) => { const d = await cdp("Page.captureScreenshot", { format: "png" }); writeFileSync(join(RUN, name), Buffer.from(d.result.data, "base64")); return join(RUN, name); };

await cdp("Network.enable");
await cdp("Page.enable");
await cdp("Emulation.setDeviceMetricsOverride", { width: 1400, height: 900, deviceScaleFactor: 1, mobile: false });
// Long tasks (main thread busy > 50 ms) and the moment the first tile shows a picture.
await cdp("Page.addScriptToEvaluateOnNewDocument", { source: `
  window.__perf = { longTasks: [], firstTile: null, nav: performance.timeOrigin };
  try { new PerformanceObserver((list) => { for (const e of list.getEntries()) window.__perf.longTasks.push({ t: e.startTime, d: e.duration }); }).observe({ type: "longtask", buffered: true }); } catch {}
  const mo = new MutationObserver(() => {
    if (window.__perf.firstTile !== null) return;
    const img = document.querySelector('.cell[data-slot="grid"] img');
    if (img && img.complete && img.naturalWidth > 0) { window.__perf.firstTile = performance.now(); mo.disconnect(); }
  });
  document.addEventListener("DOMContentLoaded", () => mo.observe(document.body, { subtree: true, childList: true, attributes: true }));
` });

const STATE = `(() => {
  const cells = [...document.querySelectorAll('#grid .cell')];
  const vh = window.innerHeight;
  const visible = cells.filter((c) => { const r = c.getBoundingClientRect(); return r.bottom > 0 && r.top < vh; });
  const shows = (c) => { const img = c.querySelector("img"); return !!(img && !img.hidden && img.complete && img.naturalWidth > 0); };
  return { cells: cells.length, visible: visible.length, visibleShown: visible.filter(shows).length,
    people: document.querySelectorAll("#people-list .person-row").length,
    pressed: [...document.querySelectorAll('#people-list .person-row[aria-pressed="true"]')].map((b) => b.dataset.personId),
    stars: document.getElementById("filter-stars")?.getAttribute("aria-pressed") === "true",
    longTaskMs: window.__perf ? window.__perf.longTasks.reduce((s, e) => s + e.d, 0) : null,
    longTasks: window.__perf ? window.__perf.longTasks.length : null,
    firstTile: window.__perf ? window.__perf.firstTile : null,
    dcl: performance.getEntriesByType("navigation")[0]?.domContentLoadedEventEnd ?? null,
    now: performance.now() };
})()`;

// Wait until the grid is "settled": the cell count stopped changing and every visible tile shows a picture.
async function settle(predicate, timeoutMs = 20000) {
  const started = performance.now();
  let last = null; let stableSince = null;
  while (performance.now() - started < timeoutMs) {
    const s = await js(STATE);
    // Settled = predicate holds and every tile on screen shows a picture (or the result is empty).
    const ok = predicate(s) && (s.cells === 0 || (s.visible > 0 && s.visibleShown === s.visible));
    if (ok) {
      if (!last || last.cells !== s.cells || stableSince === null) stableSince = performance.now();
      else if (performance.now() - stableSince > 150) return { state: s, ms: +(performance.now() - started - 150).toFixed(0) };
    } else stableSince = null;
    last = s;
    await sleep(25);
  }
  const state = await js(STATE);
  state.unshownSample = await js(`[...document.querySelectorAll('.cell[data-slot="grid"]')].filter((c) => { const r = c.getBoundingClientRect(); return r.bottom > 0 && r.top < innerHeight; })
    .filter((c) => { const img = c.querySelector("img"); return !(img && !img.hidden && img.complete && img.naturalWidth > 0); }).slice(0, 3)
    .map((c) => ({ cls: c.className, html: c.innerHTML.slice(0, 200) }))`);
  return { state, ms: null, timedOut: true };
}

async function measure(name, action, predicate) {
  const before = await js(STATE);
  const finishedBefore = finished.length;
  const t0 = performance.now();
  await action();
  const done = await settle(predicate);
  const all = finished.slice(finishedBefore);
  const requests = all.filter((r) => /\/api\/(items|groups|people|tags|jobs|sources|settings)/.test(r.url))
    .map((r) => ({ path: r.url.replace(BASE, "").slice(0, 90), ms: r.ms }));
  const media = { thumb: 0, face: 0, other: 0 };
  for (const r of all.filter((r) => /\/api\/media\//.test(r.url))) { const w = /which=(\w+)/.exec(r.url)?.[1]; media[w in media ? w : "other"] += 1; }
  const row = { name, settleMs: done.ms, timedOut: !!done.timedOut, cellsBefore: before.cells, cellsAfter: done.state.cells,
    longTaskMsDuring: done.state.longTaskMs - before.longTaskMs, longTasksDuring: done.state.longTasks - before.longTasks,
    apiRequests: requests.length, mediaRequests: media, slowestApi: requests.sort((a, b) => b.ms - a.ms).slice(0, 3) };
  console.log(JSON.stringify(row));
  return row;
}

async function phase(tag) {
  const rows = [];
  // First load: fresh navigation with an empty HTTP cache.
  await cdp("Network.clearBrowserCache");
  const navStart = performance.now();
  await cdp("Page.navigate", { url: BASE + "/" });
  const loaded = await settle((st) => st.cells > 0 && st.people > 0, 30000);
  const s = loaded.state;
  rows.push({ name: "first-load", settleMs: +(performance.now() - navStart).toFixed(0), domContentLoadedMs: s.dcl && +s.dcl.toFixed(0),
    firstTileMs: s.firstTile && +s.firstTile.toFixed(0), cells: s.cells, visibleTiles: s.visible, people: s.people,
    longTaskMs: s.longTaskMs, longTasks: s.longTasks, timedOut: !!loaded.timedOut, screenshot: await shot(`${tag}-first-load.png`) });
  console.log(JSON.stringify(rows[0]));
  const people = await js(`[...document.querySelectorAll("#people-list .person-row")].map((b) => b.dataset.personId)`);
  const click = (sel) => js(`(() => { const el = document.querySelector('${sel}'); if (!el) return false; el.click(); return true; })()`);
  const personBtn = (id) => `#people-list .person-row[data-person-id="${id}"]`;
  if (people.length >= 2) {
    const all = s.cells;
    rows.push(await measure("filter-person-1", () => click(personBtn(people[0])), (st) => st.cells < all && st.pressed.length === 1));
    rows.push(await measure("filter-person-1-off", () => click(personBtn(people[0])), (st) => st.cells === all && st.pressed.length === 0));
    rows.push(await measure("filter-person-2", () => click(personBtn(people[1])), (st) => st.cells < all && st.pressed.length === 1));
    rows.push(await measure("filter-person-1+2 (ctrl)", () => js(`(() => { const el = document.querySelector('${personBtn(people[0])}'); el.dispatchEvent(new MouseEvent("click", { bubbles: true, ctrlKey: true })); return true; })()`), (st) => st.pressed.length === 2));
    rows.push(await measure("filter-clear-people", async () => { await click(personBtn(people[0])); await click(personBtn(people[1])); }, (st) => st.pressed.length === 0 && st.cells === all));
    rows.push(await measure("chip-favorites", () => click("#filter-favorites"), (st) => st.cells !== all || true));
    rows.push(await measure("chip-all", () => click("#filter-all"), (st) => st.cells === all));
    // The fixture rates nearly every photo >= 4 stars, so the cell count barely moves; settle on the chip state.
    rows.push(await measure("chip-4-stars", () => click("#filter-stars"), (st) => st.stars && st.cells > 0));
    rows.push(await measure("chip-4-stars-off", () => click("#filter-stars"), (st) => !st.stars && st.cells === all));
    rows.push(await measure("chip-photos", () => click("#filter-photos"), (st) => true));
    rows.push(await measure("chip-all-2", () => click("#filter-all"), (st) => st.cells === all));
  } else {
    rows.push({ name: "people-missing", people: people.length });
  }
  // Open a picture and come back.
  const VIEWER = `(() => { const el = document.getElementById("viewer-original"); const st = document.getElementById("viewer-image");
    const shown = (e) => !!(e && !e.hidden && e.complete && e.naturalWidth > 0); return { original: shown(el), standIn: shown(st) }; })()`;
  const openT = performance.now();
  await js(`document.querySelectorAll('.cell[data-slot="grid"]')[5].click()`);
  let standIn = null, original = null;
  while (performance.now() - openT < 10000) {
    const v = await js(VIEWER);
    if (standIn === null && v.standIn) standIn = +(performance.now() - openT).toFixed(0);
    if (v.original) { original = +(performance.now() - openT).toFixed(0); break; }
    await sleep(20);
  }
  rows.push({ name: "open-picture", standInMs: standIn, originalMs: original, screenshot: await shot(`${tag}-viewer.png`) });
  console.log(JSON.stringify(rows.at(-1)));
  rows.push(await measure("viewer-back", () => click("#viewer-back"), (st) => st.cells > 0));
  // Raw API timing from Node, for the server side alone.
  const apiRows = {};
  for (const path of ["/api/items", `/api/items?person=${people[0] || ""}`, "/api/groups?level=years", "/api/people", "/api/tags", "/api/jobs"]) {
    const times = [];
    for (let i = 0; i < 3; i++) times.push((await api(path)).ms);
    apiRows[path.slice(0, 60)] = Math.min(...times);
  }
  rows.push({ name: "api-min-of-3-ms", ...apiRows });
  console.log(JSON.stringify(rows.at(-1)));
  return rows;
}

const result = { label, app: APP, fixture: FIXTURE, run: RUN, idle: await phase("idle") };
// Now with the AI drain busy: re-run faces on every photo.
if (sourceId) {
  await api("/api/jobs", { action: "rerun-faces" });
  await sleep(1500);
  result.processing = await phase("processing");
  result.jobsAfter = (await api("/api/jobs")).json;
}
writeFileSync(join(RUN, "result.json"), JSON.stringify(result, null, 2) + "\n");
writeFileSync(join(HERE, `ui-${label}.json`), JSON.stringify(result, null, 2) + "\n");
console.log("wrote", join(HERE, `ui-${label}.json`));
ws.close();
edge.kill();
server.kill();
process.exit(0);
