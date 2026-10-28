// Read-only browser timings against a running Library. No catalog mutations.
// Usage: node tests/perf/live_browse.cjs output.json [override-library-js]
const fs = require('fs');
const crypto = require('crypto');
const { chromium } = require('C:/Users/SLY2.0/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const url = 'http://127.0.0.1:8785';
const out = process.argv[2];
if (!out) throw Error('output path required');
const replacement = process.argv[3] && fs.readFileSync(process.argv[3]);
const sleep = ms => new Promise(r => setTimeout(r, ms));
let activeBrowser, partialResult;
async function jobs() { return fetch(url + '/api/jobs').then(r => r.json()); }
async function run() {
  const result = { timestamp: new Date().toISOString(), url, note: 'Headless Edge on server PC, 1600x900, fresh browser cache; not the tablet. Non-GET requests blocked. Image counts are visible loaded image elements, sampled after browser frames. Live background work continues.', scenarios: {}, errors: [] };
  partialResult = result;
  result.runtime = await fetch(url + '/api/runtime').then(r => r.json());
  result.jobsStart = await jobs();
  const js = replacement || Buffer.from(await fetch(url + '/assets/library.js').then(r => r.arrayBuffer()));
  result.jsSha256 = crypto.createHash('sha256').update(js).digest('hex');
  const browser = await chromium.launch({ executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless:true });
  activeBrowser = browser;
  const context = await browser.newContext({ viewport:{width:1600,height:900} });
  await context.route('**/*', async route => {
    if (!['GET','HEAD'].includes(route.request().method())) return route.fulfill({status:200,contentType:'application/json',body:'{}'});
    if (replacement && new URL(route.request().url()).pathname === '/assets/library.js') return route.fulfill({status:200,contentType:'text/javascript',body:replacement});
    return route.continue();
  });
  const page = await context.newPage();
  const cdp = await context.newCDPSession(page);
  await cdp.send('Performance.enable');
  const metrics = async () => Object.fromEntries((await cdp.send('Performance.getMetrics')).metrics.map(m => [m.name,m.value]));
  result.metrics = {};
  result.resources = [];
  page.on('requestfinished', req => {
    const u = new URL(req.url());
    if (u.pathname.startsWith('/api/media/')) result.resources.push({phase, which:u.searchParams.get('which'), timing:req.timing()});
  });
  let phase = 'initial';
  const requests = new Map();
  result.network = {};
  page.on('request', req => {
    const u = new URL(req.url());
    if (u.pathname === '/api/items/stream') requests.set(req, {phase, start:Date.now()});
  });
  page.on('response', response => {
    const r=requests.get(response.request());
    if (r) { r.headersMs=Date.now()-r.start; r.status=response.status(); r.serverTiming=response.headers()['server-timing']; }
  });
  page.on('requestfinished', req => {
    const r=requests.get(req);
    if(r) { (result.network[r.phase] ||= []).push({headersMs:r.headersMs, totalMs:Date.now()-r.start, status:r.status,serverTiming:r.serverTiming}); requests.delete(req); }
  });
  page.on('pageerror', e => result.errors.push(String(e)));
  await page.addInitScript(() => {
    window.measureViewport = async (duration) => {
      const start=window.measureStart || performance.now(), samples=[];
      window.measureStart=0;
      while (performance.now()-start < duration) {
        await new Promise(requestAnimationFrame);
        const g=document.querySelector('#grid'), b=g.getBoundingClientRect();
        const cells=[...g.querySelectorAll('.cell[data-slot="grid"]')].filter(c=>{let r=c.getBoundingClientRect();return r.width>0 && r.height>0 && r.bottom>b.top && r.top<b.bottom && r.right>b.left && r.left<b.right;});
        const painted=cells.filter(c=>{let i=c.querySelector('img');return i && !i.hidden && i.complete && i.naturalWidth>0;}).length;
        samples.push({ms:Math.round(performance.now()-start),visible:cells.length,painted,state:g.dataset.catalogState});
        if (cells.length && painted===cells.length && g.dataset.catalogState==='done') break;
        await new Promise(r=>setTimeout(r,100));
      }
      return samples;
    };
  });
  const begin=Date.now();
  await page.goto(url, {waitUntil:'domcontentloaded', timeout:60000});
  result.domContentLoadedMs=Date.now()-begin;
  result.scenarios.initial=await page.evaluate(()=>measureViewport(60000));
  result.metrics.initial = await metrics();
  console.log('initial measured');
  result.initialCells=await page.locator('#grid .cell[data-slot="grid"]').count();
  // A slow initial query must not silently turn the scroll trial into a skip.
  await page.waitForFunction(() => document.querySelector('#grid').dataset.catalogState === 'done', null, {timeout:180000});
  // Exercise the densest wall without persisting the user's settings.
  await page.selectOption('#date-group','off');
  await page.locator('#size-slider').evaluate(e=>{e.value='0';e.dispatchEvent(new Event('input',{bubbles:true}));});
  // Choose a distant already-created cell, preserving application settings.
  const scrolled=await page.evaluate(()=>{
    const grid=document.querySelector('#grid');
    const host=document.querySelector('#virtual-grid .virtual-spacer');
    window.measureStart=performance.now();
    if (host && host.offsetHeight > grid.clientHeight) {
      grid.scrollTop = host.parentNode.offsetTop + host.offsetHeight * 0.7;
      return true;
    }
    const a=grid.querySelectorAll('.cell[data-slot="grid"]');
    const c=a[Math.floor(a.length*.7)];
    if(!c)return false;
    c.scrollIntoView({block:'start'});
    return true;
  });
  phase='scroll';
  if(scrolled) result.scenarios.scroll=await page.evaluate(()=>measureViewport(15000));
  result.metrics.scroll = await metrics();
  console.log('scroll measured');
  const person=page.locator('#people-list .person-row').first();
  if (await person.count()) {
    phase='person';
    await person.evaluate(e=>{window.measureStart=performance.now();e.click();});
    result.scenarios.person=await page.evaluate(()=>measureViewport(25000));
    result.metrics.person = await metrics();
    console.log('person measured');
  } else result.personUnavailable=true;
  phase='sort';
  const sort = page.locator('#sort-presentable');
  const options = await sort.locator('option').evaluateAll(a=>a.map(o=>o.value));
  const nameOption = options.find(v=>v.toLowerCase().includes('name'));
  if(nameOption) {
    await page.evaluate(()=>{window.measureStart=performance.now();});
    await sort.selectOption(nameOption);
    result.scenarios.sort=await page.evaluate(()=>measureViewport(25000));
    result.metrics.sort = await metrics();
    console.log('sort measured');
  } else result.sortUnavailable=options;
  result.jobsEnd=await jobs();
  result.elapsedMs=Date.now()-begin;
  await browser.close();
  fs.writeFileSync(out,JSON.stringify(result,null,2));
}
run().catch(async e=>{fs.writeFileSync(out,JSON.stringify({...partialResult,error:String(e),stack:e.stack},null,2));if(activeBrowser)await activeBrowser.close();process.exitCode=1;});
