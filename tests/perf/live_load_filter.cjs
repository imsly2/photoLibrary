// Live-library load and filter benchmark, browser half. Run by live_load_filter.py.
// Read-only: non-GET requests are answered inside the browser, so sort and
// settings never reach the server.
// Usage: node tests/perf/live_load_filter.cjs <out.json> [--url http://127.0.0.1:8785] [--quick]
const fs = require('fs');
const { chromium } = require(process.env.PLAYWRIGHT_PATH
  || 'C:/Users/SLY2.0/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');

const BROWSER = process.env.BENCH_BROWSER || 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';

// Everything this benchmark knows about the page. A redesign that renames
// these updates them here and nowhere else.
const PAGE = {
  grid: '#grid',
  cell: '.cell',
  status: '#library-chrome',
  personRow: '#people-list .person-row',
  clear: '#clear-filters',
  search: '#search',
  sort: '#sort',
  importDialog: '#import-iphone',
  chips: {
    photos: '#filter-photos',
    all: '#filter-all',
    videos: '#filter-videos',
    withPeople: '#filter-with-people',
  },
};

const args = process.argv.slice(2);
const out = args[0];
if (!out) throw Error('output path required');
const url = args.includes('--url') ? args[args.indexOf('--url') + 1] : 'http://127.0.0.1:8785';
const quick = args.includes('--quick');
const OPEN_TIMEOUT = quick ? 300000 : 600000;
const CLICK_TIMEOUT = 20000;
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function countKnown(s) {
  if (s.state) return s.state === 'done';
  return s.count != null && !s.counting;
}

async function run() {
  const browser = await chromium.launch({ executablePath: BROWSER, headless: true });
  const context = await browser.newContext({ viewport: { width: 1600, height: 900 } });
  await context.route('**/*', (route) => {
    if (!['GET', 'HEAD'].includes(route.request().method())) {
      return route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
    }
    return route.continue();
  });
  await context.addInitScript((P) => {
    performance.setResourceTimingBufferSize(100000);
    const b = window.__bench = { longTasks: 0, longTaskMax: 0, frameGapMax: 0 };
    b.sample = function () {
      const grid = document.querySelector(P.grid);
      if (!grid) return { missing: true, visible: 0, painted: 0, noSrc: 0, paintedIds: [], sig: '', people: 0 };
      const box = grid.getBoundingClientRect();
      const visible = [];
      for (const cell of grid.querySelectorAll(P.cell)) {
        const r = cell.getBoundingClientRect();
        if (r.width > 0 && r.height > 0 && r.bottom > box.top && r.top < box.bottom && r.right > box.left && r.left < box.right) {
          visible.push(cell);
        }
      }
      const paintedIds = [];
      let noSrc = 0;
      for (const cell of visible) {
        const img = cell.querySelector('img');
        if (img && !img.hidden && img.complete && img.naturalWidth > 0) paintedIds.push(cell.dataset.id);
        else if (!img || !img.getAttribute('src')) noSrc += 1;
      }
      const text = (document.querySelector(P.status)?.textContent || '').replace(/\s+/g, ' ');
      const match = text.match(/([\d,]+) pictures/);
      return {
        state: grid.dataset.catalogState || '',
        visible: visible.length,
        painted: paintedIds.length,
        noSrc,
        paintedIds,
        sig: visible.slice(0, 40).map((c) => (c.dataset.slot || '') + ':' + c.dataset.id).join('|'),
        count: match ? Number(match[1].replace(/,/g, '')) : null,
        counting: /still counting/.test(text),
        people: document.querySelectorAll(P.personRow).length,
      };
    };
    // One user action, timed frame by frame inside the page so the numbers
    // carry no round trips to the test driver.
    b.phase = function (action, timeout) {
      const known = (s) => (s.state ? s.state === 'done' : s.count != null && !s.counting);
      const before = b.sample();
      const t0 = performance.now();
      if (action.type === 'click') {
        document.querySelector(action.sel).click();
      } else if (action.type === 'person') {
        let best = null;
        for (const row of document.querySelectorAll(P.personRow)) {
          const n = Number(row.querySelector('.person-count')?.textContent || 0);
          if (!best || n > best.n) best = { row, n };
        }
        if (!best) throw Error('no person row');
        best.row.click();
      } else if (action.type === 'search') {
        const input = document.querySelector(P.search);
        input.value = action.text;
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
      } else if (action.type === 'sort') {
        const el = document.querySelector(P.sort);
        el.value = action.value;
        el.dispatchEvent(new Event('change', { bubbles: true }));
      }
      return new Promise((resolve) => {
        let ready = null;
        let settled = null;
        let settledIgnoringNoSrc = null;
        let maxBlank = 0;
        let last = before;
        const step = () => {
          const s = b.sample();
          const ms = performance.now() - t0;
          last = s;
          if (ready == null && known(s) && s.visible > 0) ready = ms;
          if (ready != null) {
            maxBlank = Math.max(maxBlank, s.visible - s.painted);
            if (settled == null && s.painted === s.visible) settled = ms;
            if (settledIgnoringNoSrc == null && s.painted === s.visible - s.noSrc) settledIgnoringNoSrc = ms;
          }
          if ((settled != null && ms > settled + 300) || ms > timeout) {
            resolve({
              readyMs: ready == null ? null : Math.round(ready),
              settledMs: settled == null ? null : Math.round(settled),
              settledIgnoringNoSrcMs: settledIgnoringNoSrc == null ? null : Math.round(settledIgnoringNoSrc),
              maxBlank,
              changed: last.sig !== before.sig,
              visible: last.visible,
              unpainted: last.visible - last.painted,
              noSrc: last.noSrc,
              rows: last.count,
              paintedIds: last.paintedIds,
            });
            return;
          }
          requestAnimationFrame(step);
        };
        requestAnimationFrame(step);
      });
    };
    try {
      new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          b.longTasks += 1;
          b.longTaskMax = Math.max(b.longTaskMax, entry.duration);
        }
      }).observe({ type: 'longtask', buffered: true });
    } catch (err) { /* longtask not supported */ }
    let last = performance.now();
    const tick = () => {
      const now = performance.now();
      b.frameGapMax = Math.max(b.frameGapMax, now - last);
      last = now;
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }, PAGE);
  const page = await context.newPage();

  const media = [];
  const byRequest = new Map();
  const catalogRequests = [];
  page.on('request', (req) => {
    const u = new URL(req.url());
    if (u.pathname.startsWith('/api/media/')) {
      const row = { at: Date.now(), id: u.pathname.slice('/api/media/'.length), which: u.searchParams.get('which') || '', status: null };
      media.push(row);
      byRequest.set(req, row);
    } else if (u.pathname.startsWith('/api/items') || u.pathname === '/api/catalog/index') {
      catalogRequests.push({ at: Date.now(), path: u.pathname + u.search });
    }
  });
  page.on('response', (res) => {
    const row = byRequest.get(res.request());
    if (row) row.status = res.status();
  });
  const paintedEver = new Set();

  const sample = () => page.evaluate(() => window.__bench.sample());

  async function pageCounters(reset) {
    return page.evaluate((again) => {
      const b = window.__bench || {};
      const row = { longTasks: b.longTasks || 0, longTaskMaxMs: Math.round(b.longTaskMax || 0), frameGapMaxMs: Math.round(b.frameGapMax || 0) };
      if (again) Object.assign(b, { longTasks: 0, longTaskMax: 0, frameGapMax: 0 });
      return row;
    }, reset);
  }

  // Open: from navigation until the count is known, People has rows, and the
  // first screen is painted (or 30 s after the count, whichever is first).
  const t0 = Date.now();
  await page.goto(url, { waitUntil: 'commit', timeout: 60000 });
  const open = {
    firstCellMs: null, firstPaintMs: null, screenPaintedMs: null, countKnownMs: null,
    settledAfterCountMs: null, peopleReadyMs: null, countAt: {}, rows: null,
  };
  let last = null;
  while (Date.now() - t0 < OPEN_TIMEOUT) {
    let s;
    try { s = await sample(); } catch (err) { await sleep(100); continue; }
    const ms = Date.now() - t0;
    last = s;
    s.paintedIds.forEach((id) => paintedEver.add(id));
    const full = s.visible > 0 && s.painted === s.visible;
    if (open.firstCellMs == null && s.visible > 0) open.firstCellMs = ms;
    if (open.firstPaintMs == null && s.painted > 0) open.firstPaintMs = ms;
    if (open.screenPaintedMs == null && full) open.screenPaintedMs = ms;
    if (open.countKnownMs == null && countKnown(s) && s.visible > 0) { open.countKnownMs = ms; open.rows = s.count; }
    if (open.countKnownMs != null && open.settledAfterCountMs == null && full) open.settledAfterCountMs = ms;
    if (open.peopleReadyMs == null && s.people > 0) open.peopleReadyMs = ms;
    for (const at of [5, 10, 30, 60]) {
      if (open.countAt[at + 's'] === undefined && ms >= at * 1000) open.countAt[at + 's'] = s.count;
    }
    if (open.countKnownMs != null && open.peopleReadyMs != null
      && (open.settledAfterCountMs != null || ms - open.countKnownMs > 30000)) break;
    await sleep(100);
  }
  open.timedOut = open.countKnownMs == null;
  open.endVisible = last ? last.visible : null;
  open.endUnpainted = last ? last.visible - last.painted : null;
  open.endNoSrc = last ? last.noSrc : null;
  open.mediaRequests = media.length;
  open.catalogRequests = catalogRequests.length;
  Object.assign(open, await pageCounters(true));

  await page.evaluate((sel) => {
    const dialog = document.querySelector(sel);
    if (dialog && dialog.open) dialog.close();
  }, PAGE.importDialog).catch(() => {});
  const originalSort = await page.evaluate((sel) => document.querySelector(sel)?.value || '', PAGE.sort).catch(() => '');

  async function phase(label, action) {
    const res = { label };
    try {
      await pageCounters(true);
      const seen = new Set(paintedEver);
      const mediaMark = media.length;
      const catalogMark = catalogRequests.length;
      const timed = await page.evaluate(([a, ms]) => window.__bench.phase(a, ms), [action, CLICK_TIMEOUT]);
      timed.paintedIds.forEach((id) => paintedEver.add(id));
      delete timed.paintedIds;
      const reqs = media.slice(mediaMark);
      Object.assign(res, timed, {
        settledTimedOut: timed.settledMs == null,
        mediaRequests: reqs.length,
        revalidated: reqs.filter((r) => r.status === 304).length,
        redownloads: reqs.filter((r) => seen.has(r.id)).length,
        catalogRequests: catalogRequests.length - catalogMark,
      }, await pageCounters(false));
    } catch (err) {
      res.error = String((err && err.message) || err).slice(0, 300);
    }
    await sleep(500);
    return res;
  }

  const click = (sel) => ({ type: 'click', sel });
  const steps = [
    ['photos', click(PAGE.chips.photos)],
    ['all', click(PAGE.chips.all)],
    ['videos', click(PAGE.chips.videos)],
    ['all2', click(PAGE.chips.all)],
    ['withPeople', click(PAGE.chips.withPeople)],
    ['clearWithPeople', click(PAGE.clear)],
    ['person', { type: 'person' }],
    ['clearPerson', click(PAGE.clear)],
  ];
  if (!quick) {
    const other = originalSort === 'name' ? 'date' : 'name';
    steps.push(
      ['search', { type: 'search', text: '2019' }],
      ['clearSearch', click(PAGE.clear)],
      ['sortOther', { type: 'sort', value: other }],
      ['sortBack', { type: 'sort', value: originalSort || 'date' }],
    );
  }
  const phases = {};
  for (const [label, action] of steps) phases[label] = await phase(label, action);

  const result = {
    timestamp: new Date().toISOString(),
    url,
    quick,
    viewport: '1600x900 headless Edge',
    openTimeoutMs: OPEN_TIMEOUT,
    clickTimeoutMs: CLICK_TIMEOUT,
    originalSort,
    open,
    phases,
    mediaTotal: media.length,
  };
  fs.writeFileSync(out, JSON.stringify(result, null, 2));
  await browser.close();
}

run().catch((error) => {
  console.error(error);
  process.exit(1);
});
