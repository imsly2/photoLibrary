import hashlib,json,subprocess,types,shutil
from pathlib import Path
from library.service import Library
from library.catalog_io import iter_item_ids,load_item
from tests.qa.roots import prepare_root

out=Path(__file__).parent/'heic-baseline'
out.mkdir(exist_ok=False)
src=subprocess.run(['git','show','HEAD:library/renditions.py'],capture_output=True,text=True,check=True).stdout
(out/'HEAD-renditions.py').write_text(src,encoding='utf-8')
module=types.ModuleType('library.renditions_baseline')
module.__file__=str(out/'HEAD-renditions.py')
exec(compile(src,module.__file__,'exec'),module.__dict__)
media=out/'media';media.mkdir()
for name in ['quad.heic','quad.heif','broken.heic']:
    shutil.copyfile(Path('tests/fixtures/media/formats')/name,media/name)
root=prepare_root(out/'library-data')
lib=Library(root)
summary=lib.scan({'path':str(media.resolve()),'mode':'serve-from-there','previewStore':'with-server'})
for _ in range(10):
    if not module.drain_step(root):break
record={'baseline':'git show HEAD:library/renditions.py','sourceSha256':hashlib.sha256(src.encode()).hexdigest(),'summary':summary,'items':[],'independentFFmpeg':[]}
for item_id in iter_item_ids(root):
    item=load_item(root,item_id)
    record['items'].append({'file':item['filename'],'renditions':item['renditions']})
for name in ['quad.heic','quad.heif','broken.heic']:
    target=out/(name+'.webp')
    proc=subprocess.run(['ffmpeg','-v','error','-y','-i',str(media/name),'-frames:v','1','-f','webp',str(target)],capture_output=True,text=True)
    record['independentFFmpeg'].append({'file':name,'exit':proc.returncode,'stderr':proc.stderr,'bytes':target.stat().st_size if target.exists() else 0})
(out/'result.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
print(json.dumps(record,indent=2))
