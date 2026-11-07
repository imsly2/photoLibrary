// Time the first pictures when switching between the full grid and one person.
// Read-only. Non-GET requests are blocked. The live server keeps running.
// Usage: node tests/perf/filter_switch.cjs output.json
const fs = require('fs');
const { chromium } = require('C:/Users/SLY2.0/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');

const url = 'http://127.0.0.1:8785';
const out = process.argv[2];
if (!out) throw Error('output path required');

async function run() {
  const result = {
    timestamp: new Date().toISOString(),
    url,
    note: 'Headless Edge, 1600x900. Faces may be running. No catalog writes.',
    phases: {},
  };
  const browser = await chromium.launch({
    executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
    headless: true,
  });
  const context = await browser.newContext({ viewport: { width: 1600, height: 900 } });
  await context.route('**/*', async (route) => {
    if (!['GET', 'HEAD'].includes(route.request().method())) {
      return route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
    }
    return route.continue();
  });
  const page = await context.newPage();
  const streams = [];
  page.on('response', async (response) => {
    const u = new URL(response.url());
    if (u.pathname !== '/api/items/stream') return;
    streams.push({
      at: Date.now(),
      query: u.search,
      status: response.status(),
      serverTiming: response.headers()['server-timing'] || '',
    });
  });
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForFunction(() => document.querySelector('#grid')?.dataset.catalogState === 'done', null, { timeout: 180000 });
  await page.evaluate(() => {
    const dialog = document.getElementById('import-iphone');
    if (dialog && dialog.open) dialog.close();
  });
  await page.waitForTimeout(1500);

  async function sample(label) {
    return page.evaluate((name) => {
      const grid = document.querySelector('#grid');
      const box = grid.getBoundingClientRect();
      const cells = [...grid.querySelectorAll('.cell[data-slot="grid"]')];
      const visible = cells.filter((cell) => {
        const rect = cell.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0 && rect.bottom > box.top && rect.top < box.bottom && rect.right > box.left && rect.left < box.right;
      });
      const painted = (list) => list.filter((cell) => {
        const image = cell.querySelector('img');
        return image && !image.hidden && image.complete && image.naturalWidth > 0;
      }).length;
      const resources = performance.getEntriesByType('resource').filter((entry) => entry.name.includes('/api/media/'));
      return {
        label: name,
        state: grid.dataset.catalogState || '',
        dom: cells.length,
        visible: visible.length,
        paintedVisible: painted(visible),
        paintedDom: painted(cells),
        media: resources.length,
        mediaTransfer: Math.round(resources.reduce((sum, entry) => sum + (entry.transferSize || 0), 0)),
        mediaDecoded: Math.round(resources.reduce((sum, entry) => sum + (entry.decodedBodySize || 0), 0)),
      };
    }, label);
  }

  async function watch(label, ms) {
    const started = Date.now();
    const rows = [];
    let firstCell = null;
    let firstPaint = null;
    let paint70 = null;
    let settled = null;
    while (Date.now() - started < ms) {
      const row = await sample(label);
      row.ms = Date.now() - started;
      rows.push(row);
      if (firstCell == null && row.dom > 0) firstCell = row.ms;
      if (firstPaint == null && row.paintedVisible > 0) firstPaint = row.ms;
      if (paint70 == null && row.paintedVisible >= 70) paint70 = row.ms;
      if (settled == null && row.visible > 0 && row.paintedVisible === row.visible && row.state === 'done') settled = row.ms;
      if (settled != null && row.ms > settled + 400) break;
      await page.waitForTimeout(100);
    }
    const media = await page.evaluate(() => performance.getEntriesByType('resource')
      .filter((entry) => entry.name.includes('/api/media/'))
      .map((entry) => ({
        dur: Math.round(entry.duration),
        transfer: entry.transferSize || 0,
        decoded: entry.decodedBodySize || 0,
        start: Math.round(entry.startTime),
      })));
    return { rows, firstCell, firstPaint, paint70, settled, mediaCount: media.length };
  }

  const before = await sample('warm');
  const people = await page.evaluate(() => [...document.querySelectorAll('#people-list .person-row')].map((row) => ({
    id: row.dataset.personId,
    name: row.querySelector('.person-name')?.textContent || '',
    count: Number(row.querySelector('.person-count')?.textContent || 0),
  })));
  const unnamed = people.filter((person) => /unnamed/i.test(person.name) && person.count > 100)
    .sort((a, b) => b.count - a.count)[0] || people.filter((person) => /unnamed/i.test(person.name))[0] || people[0];
  result.person = unnamed;
  result.people = people.length;
  if (!unnamed) throw Error('no person row');

  const streamMark = streams.length;
  const mediaMark = before.media;
  const filterClickAt = Date.now();
  await page.locator(`#people-list .person-row[data-person-id="${unnamed.id}"]`).click({ timeout: 60000 });
  result.phases.filterClickMs = Date.now() - filterClickAt;
  result.phases.filter = await watch('filter', 45000);
  result.phases.filter.newMedia = result.phases.filter.mediaCount - mediaMark;
  result.phases.filter.streams = streams.slice(streamMark);

  const clear = page.locator('#clear-filters');
  if (await clear.count()) {
    const mark = streams.length;
    const mediaAtClear = (await sample('before-clear')).media;
    const clearClickAt = Date.now();
    await clear.click({ timeout: 60000 });
    result.phases.clearClickMs = Date.now() - clearClickAt;
    result.phases.clear = await watch('clear', 45000);
    result.phases.clear.newMedia = result.phases.clear.mediaCount - mediaAtClear;
    result.phases.clear.streams = streams.slice(mark);
  }
  result.warm = before;
  await browser.close();
  fs.writeFileSync(out, JSON.stringify(result, null, 2));
  const brief = (phase) => phase && {
    firstCell: phase.firstCell,
    firstPaint: phase.firstPaint,
    paint70: phase.paint70,
    settled: phase.settled,
    newMedia: phase.newMedia,
    last: phase.rows[phase.rows.length - 1],
    streams: phase.streams,
  };
  console.log(JSON.stringify({
    person: unnamed,
    filterClickMs: result.phases.filterClickMs,
    clearClickMs: result.phases.clearClickMs,
    filter: brief(result.phases.filter),
    clear: brief(result.phases.clear),
  }, null, 2));
}

run().catch((error) => {
  console.error(error);
  process.exit(1);
});
