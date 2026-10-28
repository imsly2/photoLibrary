// Observe background face throughput without changing processing state or media.
// Usage: node tests/perf/live_faces.cjs output.json [duration-seconds]
const fs = require('fs');
const out=process.argv[2], seconds=Number(process.argv[3] || 60);
if(!out || !Number.isFinite(seconds) || seconds < 5) throw Error('output path and duration >= 5 seconds required');
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
  const start=Date.now(), samples=[];
  while(Date.now()-start < seconds*1000) {
    const body=await fetch('http://127.0.0.1:8785/api/jobs').then(r=>{if(!r.ok)throw Error('jobs '+r.status);return r.json();});
    const face=(body.queues||[]).find(q=>q.id==='infer-faces');
    if(!face)throw Error('face queue unavailable');
    samples.push({ms:Date.now()-start,done:face.done,pending:face.pending,errors:face.error,state:face.state,paused:body.paused});
    await sleep(Math.min(5000,Math.max(0,seconds*1000-(Date.now()-start))));
  }
  const body=await fetch('http://127.0.0.1:8785/api/jobs').then(r=>r.json());
  const face=body.queues.find(q=>q.id==='infer-faces');
  samples.push({ms:Date.now()-start,done:face.done,pending:face.pending,errors:face.error,state:face.state,paused:body.paused});
  fs.writeFileSync(out,JSON.stringify({timestamp:new Date().toISOString(),note:'Observed queue counters, not isolated model timings. Other clients and processing affect throughput.',samples},null,2));
})().catch(e=>{fs.writeFileSync(out,JSON.stringify({error:String(e)},null,2));process.exitCode=1;});
