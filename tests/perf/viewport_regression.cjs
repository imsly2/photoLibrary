// Synthetic browser proof for dense status rotation and scroll cancellation.
const fs=require('fs'), http=require('http'), path=require('path');
const {chromium}=require('C:/Users/SLY2.0/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const root=path.resolve(__dirname,'../..'), mode=process.argv[2]||'after';
const source=fs.readFileSync(mode==='before'?'.qa/live-dense-baseline.js':'library/web/assets/library.js');
const rows=Array.from({length:900},(_,i)=>({id:'i'+String(i).padStart(4,'0'),kind:'photo',filename:'pic'+i+'.jpg',capturedAt:'2024-06-12',available:true,entities:{people:[],places:[],things:[]},renditions:{status:{thumb:'queued',preview:'ready'}}}));
let statuses=[],statusBatches=[],media=[], slowMedia=false;
const server=http.createServer((req,res)=>{
 const u=new URL(req.url,'http://fixture');
 const send=(body,type='application/json',status=200)=>{if(res.destroyed)return;res.writeHead(status,{'Content-Type':type,'Cache-Control':'no-store'});res.end(type==='application/json'?JSON.stringify(body):body);};
 if(u.pathname==='/api/items/stream')return send(JSON.stringify({type:'start'})+'\n'+rows.map(item=>JSON.stringify({type:'item',item})).join('\n')+'\n'+JSON.stringify({type:'done',count:rows.length})+'\n','application/x-ndjson');
 if(u.pathname==='/api/rendition-status'){const ids=(u.searchParams.get('ids')||'').split(',');statuses.push(...ids);statusBatches.push({count:ids.length,first:ids[0],last:ids[ids.length-1]});return send({items:ids.map(id=>({id,status:{thumb:'queued',preview:'ready'}}))});}
 if(u.pathname.startsWith('/api/media/')){if(!slowMedia)return send('', 'text/plain',404);let event={id:u.pathname.split('/').pop(),start:Date.now()};media.push(event);res.on('close',()=>{event.closed=Date.now();event.aborted=!event.sent;});return setTimeout(()=>{event.sent=Date.now();send('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><rect width="100" height="100"/></svg>','image/svg+xml');},4000);}
 if(u.pathname==='/api/settings')return send({sort:'date',dir:'desc',zoomLevel:'days',language:'en',playProxies:'off'});
 if(u.pathname==='/api/people')return send({people:[]});
 if(u.pathname==='/api/tags')return send({tags:[]});
 if(u.pathname==='/api/jobs')return send({paused:true,queues:[]});
 if(u.pathname==='/api/activity')return send({scan:{phase:'idle'}});
 if(u.pathname==='/api/health')return send({ok:true});
 if(u.pathname.startsWith('/api/'))return send([]);
 if(u.pathname==='/assets/library.js')return send(source,'text/javascript');
 const f=path.join(root,'library/web',u.pathname==='/'?'index.html':u.pathname.replace(/^\//,''));
 if(fs.existsSync(f))return send(fs.readFileSync(f),f.endsWith('.js')?'text/javascript':f.endsWith('.css')?'text/css':f.endsWith('.html')?'text/html':'image/png');
 send('', 'text/plain',404);
});
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});
 const page=await browser.newPage({viewport:{width:1600,height:900}});
 try {
  await page.goto('http://127.0.0.1:'+server.address().port+'/',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>document.querySelector('#grid')?.dataset.catalogState==='done',{timeout:30000});
  await page.selectOption('#date-group','off');
  await page.locator('#size-slider').evaluate(e=>{e.value='0';e.dispatchEvent(new Event('input',{bubbles:true}));});
  await sleep(5000);
  const covered=new Set(statuses).size;
  slowMedia=true;
  await page.reload({waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>document.querySelector('#grid')?.dataset.catalogState==='done',{timeout:30000});
  await page.selectOption('#date-group','off');
  await page.locator('#size-slider').evaluate(e=>{e.value='0';e.dispatchEvent(new Event('input',{bubbles:true}));});
  await sleep(200);
  const before=media.length;
  const beforeStats=await page.evaluate(()=>libraryTest.stillStats());
  await page.locator('#grid .cell[data-slot="grid"]').last().evaluate(e=>e.scrollIntoView({block:'end'}));
  await sleep(500);
  const aborted=media.slice(0,before).filter(x=>x.aborted).length;
  const result={mode,uniqueStatusIds:covered,statusBatches,requests:media.length,media,beforeStats,afterStats:await page.evaluate(()=>libraryTest.stillStats()),oldRequestsAborted:aborted,grid:await page.locator('#grid').evaluate(e=>({size:e.dataset.size,level:e.dataset.level,scroll:e.scrollTop,height:e.scrollHeight,client:e.clientHeight})),checks:{denseStatusCoverage:covered>80},knownGap:{offscreenRequestsCancelled:aborted>0}};
  console.log(JSON.stringify(result));
  if(mode!=='before'&&Object.values(result.checks).some(v=>!v))process.exitCode=1;
 } finally {await browser.close();server.close();}
})().catch(e=>{console.error(e);server.close();process.exitCode=1;});
