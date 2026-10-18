// Add a fresh folder with the page open (headless Edge over CDP) and watch what Steve sees:
// how soon the top 20 tiles show pictures, whether any tile ever blanks, what the viewer
// shows for a photo opened early, and how long all processing takes.
// usage: node check.mjs <app-dir> <label> <port> [count]
import { spawn } from "node:child_process";
import { copyFileSync, mkdirSync, openSync, readdirSync, writeFileSync, existsSync } from "node:fs";
import { join, resolve } from "node:path";

const [, , appArg, label, portArg, countArg = "120"] = process.argv;
const APP = resolve(appArg);
const PORT = Number(portArg);
const COUNT = Number(countArg);
const TOP = 20;
const BASE = `http://127.0.0.1:${PORT}`;
const SRC = "J:\\Pictures\\1. Favorites Pictures";
const RUN = resolve(`.qa/camera-tiles/run-${label}-${new Date().toTimeString().slice(0, 8).replace(/:/g, "")}`);
const MEDIA = join(RUN, "media");
const ROOT = join(RUN, "library-data");
mkdirSync(MEDIA, { recursive: true });
mkdirSync(ROOT, { recursive: true });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const pics = readdirSync(SRC).filter((n) => /\.jpe?g$/i.test(n)).sort();
const step = Math.max(1, Math.floor(pics.length / COUNT));
for (const name of pics.filter((_, i) => i % step === 0).slice(0, COUNT)) copyFileSync(join(SRC, name), join(MEDIA, name));
writeFileSync(join(ROOT, "settings.json"), JSON.stringify({ schemaVersion: 1, port: PORT, listenHost: "127.0.0.1",
  addFolderDefault: "ask", language: "en", sort: "date", dir: "desc" }) + "\n");

const server = spawn("J:\\slyOS\\projects\\photoLibrary\\.venv\\Scripts\\python.exe", ["-m", "library", "--root", ROOT, "serve"],
  { cwd: APP, env: { ...process.env, PATH: "C:\\ffmpeg\\bin;" + process.env.PATH, PYTHONPATH: APP },
    stdio: ["ignore", openSync(join(RUN, "server.out.log"), "w"), openSync(join(RUN, "server.err.log"), "w")] });
const api = async (path, body) => (await fetch(BASE + path, body === undefined ? {} :
  { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })).json();
for (let i = 0; i < 150; i++) { try { await api("/api/health"); break; } catch { await sleep(200); } }

const CDP_PORT = 9300 + (PORT % 100);
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
const originals = [];
ws.addEventListener("message", (m) => {
  const d = JSON.parse(m.data);
  if (pending.has(d.id)) { pending.get(d.id)(d); pending.delete(d.id); }
  if (d.method === "Network.requestWillBeSent" && /which=original/.test(d.params.request.url)) originals.push(d.params.request.url);
});
const cdp = (method, params = {}) => new Promise((r) => { const id = ++seq; pending.set(id, r); ws.send(JSON.stringify({ id, method, params })); });
const js = async (expr) => (await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true })).result?.result?.value;
const shot = async (name) => { const d = await cdp("Page.captureScreenshot", { format: "png" }); writeFileSync(join(RUN, name), Buffer.from(d.result.data, "base64")); return name; };

await cdp("Network.enable");
await cdp("Emulation.setDeviceMetricsOverride", { width: 1400, height: 900, deviceScaleFactor: 1, mobile: false });
await cdp("Page.navigate", { url: BASE + "/" });
await sleep(2500);

const TILES = `(() => [...document.querySelectorAll('.cell[data-slot="grid"]')].map((c) => {
  const img = c.querySelector("img");
  const shows = !!(img && !img.hidden && img.complete && img.naturalWidth > 0);
  const src = shows ? img.getAttribute("data-still") || "" : "";
  return [c.dataset.id, shows ? (src.includes("which=camera") ? "camera" : "thumb") : ""];
}))()`;
const VIEWER = `(() => {
  const layer = (id) => { const el = document.getElementById(id); const r = el.getBoundingClientRect();
    return { shown: !el.hidden && el.complete && el.naturalWidth > 0, which: el.getAttribute("data-which"),
      x: Math.round(r.left), y: Math.round(r.top), w: Math.round(r.width), h: Math.round(r.height) }; };
  const ph = document.getElementById("viewer-placeholder");
  return { standIn: layer("viewer-image"), original: layer("viewer-original"), placeholder: ph.hidden ? null : ph.textContent };
})()`;

const t0 = Date.now();
await api("/api/sources", { path: MEDIA, mode: "serve-from-there", previewStore: "with-server" });
const sec = () => +((Date.now() - t0) / 1000).toFixed(2);
const timeline = [];
const everShown = new Set();
let blanks = 0;
let topFull = null;
let viewer = null;
const shots = {};
while (sec() < 240) {
  const tiles = (await js(TILES)) || [];
  for (const [id, kind] of tiles) {
    if (kind) everShown.add(id);
    else if (everShown.has(id)) { blanks += 1; everShown.delete(id); }
  }
  const top = tiles.slice(0, TOP);
  const topShown = top.filter(([, kind]) => kind).length;
  const camera = tiles.filter(([, kind]) => kind === "camera").length;
  timeline.push({ t: sec(), tiles: tiles.length, shown: tiles.filter(([, k]) => k).length, camera, topShown });
  if (topFull === null && top.length === TOP && topShown === TOP) { topFull = sec(); shots.topFull = await shot("grid-top-full.png"); }
  if (!shots.early && sec() >= 3) shots.early = await shot("grid-3s.png");
  if (!viewer && topFull !== null) {
    const listed = (await api("/api/items")).filter((i) => tiles.some(([id]) => id === i.id));
    const pixels = (i) => (i.metadata?.width || 0) * (i.metadata?.height || 0);
    const largest = listed.reduce((a, b) => (pixels(b) > pixels(a) ? b : a));
    viewer = [];
    for (const [pick, why] of [[tiles[6][0], "early tile"], [largest.id, `largest (${largest.metadata.width}x${largest.metadata.height})`]]) {
    const opened = Date.now();
    originals.length = 0;
    await js(`document.querySelector('.cell[data-slot="grid"][data-id="${pick}"]').click()`);
    let first = null, standInAt = null, originalAt = null, last = null;
    while (Date.now() - opened < 8000) {
      last = await js(VIEWER);
      first = first || last;
      if (standInAt === null && last.standIn.shown) standInAt = Date.now() - opened;
      if (originalAt === null && last.original.shown) { originalAt = Date.now() - opened; break; }
      await sleep(25);
    }
    await sleep(300);
    const done = await js(VIEWER);
    const sameBox = done.standIn.w === 0 || (Math.abs(done.standIn.x - done.original.x) <= 1 && Math.abs(done.standIn.w - done.original.w) <= 1
      && Math.abs(done.standIn.h - done.original.h) <= 1);
    viewer.push({ item: pick, why, openedAtSec: +((opened - t0) / 1000).toFixed(2), standIn: done.standIn.which,
      standInMs: standInAt, originalMs: originalAt, firstPlaceholder: first.placeholder, sameBox,
      originalRequests: originals.length, screenshot: await shot(`viewer-${viewer.length + 1}.png`) });
    await js(`document.getElementById("viewer-back").click()`);
    await sleep(200);
    }
  }
  const jobs = await api("/api/jobs");
  const activity = await api("/api/activity");
  const rend = jobs.queues.find((q) => q.id === "renditions");
  if (tiles.length >= COUNT && rend.pending === 0 && activity.scan.phase === "idle") {
    timeline.at(-1).renditionsDone = rend.done;
    break;
  }
  await sleep(250);
}
const items = await api("/api/items");
const previews = items.filter((i) => i.renditions.status.preview === "ready").length;
const notApplicable = items.filter((i) => i.renditions.status.preview === "not-applicable").length;
const logs = join(ROOT, "logs", "processing");
const scanning = timeline.filter((p) => p.tiles > 0 && p.tiles < COUNT);
const result = { label, app: APP, pictures: COUNT, top20AllPicturesSec: topFull, tilesBlanked: blanks,
  firstCameraTileSec: timeline.find((p) => p.camera > 0)?.t ?? null,
  tilesWithoutPictureWhileScanning: { average: +(scanning.reduce((s, p) => s + p.tiles - p.shown, 0) / Math.max(1, scanning.length)).toFixed(1),
    worst: Math.max(0, ...scanning.map((p) => p.tiles - p.shown)), polls: scanning.length },
  everythingDoneSec: sec(),
  previewsMade: previews, previewsNotApplicable: notApplicable, viewer, screenshots: shots,
  processingLog: existsSync(logs) ? readdirSync(logs).map((n) => join(logs, n)) : [], timeline };
writeFileSync(join(RUN, "result.json"), JSON.stringify(result, null, 2) + "\n");
console.log(JSON.stringify({ ...result, timeline: undefined, run: RUN }, null, 2));
ws.close();
edge.kill();
server.kill();
process.exit(0);
