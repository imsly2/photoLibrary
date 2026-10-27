import json,time
from pathlib import Path
from playwright.sync_api import sync_playwright

base=Path(__file__).parent
out=base/'browser-final-3'
out.mkdir(exist_ok=False)
demo=base/'browser-demo-final'
ready=json.loads((demo/'ready.json').read_text(encoding='utf-8'))
record={'assertions':[],'console':[],'networkFailures':[],'httpErrors':[]}
def check(name,ok,detail=None):
    record['assertions'].append({'name':name,'pass':bool(ok),'detail':detail})
def snapshot(page,label):
    state=page.evaluate("""() => ({status:document.querySelector('#jobs-status').textContent,queues:document.querySelector('#jobs-queues').textContent,pauseDisabled:document.querySelector('#jobs-pause').disabled,resumeText:document.querySelector('#jobs-resume').textContent,thumbs:window.libraryTest.gridThumbs(),polling:window.libraryTest.polling()})""")
    record[label]=state
    page.screenshot(path=str(out/(label+'.png')),full_page=True)
    return state

with sync_playwright() as p:
    browser=p.chromium.launch()
    page=browser.new_page(viewport={'width':1440,'height':1000})
    page.on('console',lambda m:record['console'].append({'type':m.type,'text':m.text}))
    page.on('pageerror',lambda e:record['console'].append({'type':'pageerror','text':str(e)}))
    page.on('requestfailed',lambda r:record['networkFailures'].append({'url':r.url,'error':r.failure}))
    page.on('response',lambda r:record['httpErrors'].append({'url':r.url,'status':r.status}) if r.status>=400 else None)
    page.add_init_script("""(() => {const original=window.fetch;window.pollEvidence={active:{},max:{},calls:{}};window.fetch=function(...args){const url=String(args[0]);const method=(args[1]||{}).method||'GET';const key=method+' '+url;const e=window.pollEvidence;e.active[key]=(e.active[key]||0)+1;e.calls[key]=(e.calls[key]||0)+1;e.max[key]=Math.max(e.max[key]||0,e.active[key]);return original.apply(this,args).finally(()=>{e.active[key]--;});};})();""")
    page.goto(ready['url'],wait_until='domcontentloaded')
    page.wait_for_function("() => window.libraryTest && window.libraryTest.gridThumbs().painted===3")
    page.wait_for_function("name => document.querySelector('#jobs-status').textContent.includes(name)",arg=ready['file'])
    en=snapshot(page,'processing-en')
    check('en-file-derivative-elapsed',ready['file'] in en['status'] and 'preview' in en['status'].lower() and 's' in en['status'],en['status'])
    check('en-counts-setup',all(x in en['queues'] for x in ['done','waiting','errors','Setup needed']),en['queues'])
    check('preview-painting',en['thumbs']['painted']==3,en['thumbs'])
    page.locator('#jobs-pause').click()
    page.wait_for_function("() => document.querySelector('#jobs-resume').textContent==='Resume'")
    paused=snapshot(page,'paused-en')
    check('pause-responds-before-encoder-release',not (demo/'release').exists() and paused['pauseDisabled'] and 'Paused after this file' in paused['status'],paused)
    page.locator('#jobs-resume').click()
    page.wait_for_function("() => !document.querySelector('#jobs-pause').disabled")
    page.locator('#language').select_option('zh-Hans')
    page.wait_for_function("() => document.documentElement.lang==='zh-Hans'")
    zh=snapshot(page,'processing-zh')
    check('zh-counts-and-preview',all(x in zh['queues'] for x in ['已完成','等待','错误','需要安装或已停用']) and ready['file'] in zh['status'],zh)
    page.locator('#language').select_option('en')
    page.wait_for_timeout(1400)
    page.evaluate("() => {window.pollEvidence={active:{},max:{},calls:{}};}")
    page.route('**/api/jobs',lambda route:(time.sleep(2.5),route.continue_()) if route.request.method=='GET' else route.continue_())
    page.wait_for_timeout(7500)
    evidence=page.evaluate('() => window.pollEvidence')
    record['pollingSlowJobs']=evidence
    check('one-jobs-poll-in-flight',evidence['max'].get('GET /api/jobs',0)==1,evidence)
    check('one-activity-poll-in-flight',evidence['max'].get('GET /api/activity',0)==1,evidence)
    check('activity-independent-of-slow-jobs',evidence['calls'].get('GET /api/activity',0)>evidence['calls'].get('GET /api/jobs',0),evidence)
    page.unroute('**/api/jobs')
    (demo/'release').touch()
    page.wait_for_timeout(3000)
    snapshot(page,'after-release-en')
    browser.close()
record['pass']=all(x['pass'] for x in record['assertions'])
(out/'browser-result.json').write_text(json.dumps(record,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps({'pass':record['pass'],'assertions':record['assertions']},ensure_ascii=False))


