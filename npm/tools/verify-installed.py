#!/usr/bin/env python3
"""Verify an exact prepared tarball in a new consumer, with an explicit Node binary."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile

ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--candidate',type=Path,required=True)
ap.add_argument('--node',type=Path,required=True)
ap.add_argument('--out',type=Path,required=True)
ap.add_argument('--registry-install',action='store_true',help='Install the exact version by name from public npm after publication')
a=ap.parse_args();root=Path(__file__).resolve().parents[1]
a.candidate=a.candidate.resolve();a.node=a.node.resolve();a.out=a.out.resolve()
if a.out.exists():raise ValueError('Use a new consumer directory')
manifest=json.loads((a.candidate/'facade-npm.json').read_bytes());row=manifest['packages'][0]
if row['name']!='@arxo/canon-fide-chess':raise ValueError('Unexpected distribution')
archive=a.candidate/row['file'];raw=archive.read_bytes()
if len(raw)!=row['bytes'] or hashlib.sha256(raw).hexdigest()!=row['sha256']:raise ValueError('Candidate hash/size mismatch')
allowed={'src','types','data','models.json','index.d.ts','source-pin.json','canon-packages.json','examples','assets','README.md','LICENSE','NOTICE','PUBLISHING.md','package.json'}
inventory=[]
with tarfile.open(archive) as tar:
    for member in tar.getmembers():
        path=Path(member.name)
        if not member.isfile() or path.parts[0]!='package' or path.parts[1] not in allowed or '..' in path.parts:
            raise ValueError('Unexpected archive member: '+member.name)
        data=tar.extractfile(member).read()
        if any(part in path.parts for part in ['node_modules','__pycache__','tools','test','sources']):
            raise ValueError('Authoring/cache material: '+member.name)
        if any(value in data for value in [b'/Users/',b'/private/var/',b'/tmp/']):
            raise ValueError('Machine path: '+member.name)
        inventory.append({'path':member.name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
    for name in ['LICENSE','NOTICE']:
        if not any(p['path']=='package/'+name and p['bytes']>0 for p in inventory):raise ValueError('Missing '+name)
a.out.mkdir(parents=True)
(a.out/'package.json').write_text(json.dumps({'private':True,'type':'module',
    'dependencies':{'@arxo/canon-fide-chess':'0.1.0' if a.registry_install else 'file:'+str(archive),'@arxo/law':'0.4.3'},
    'devDependencies':{'typescript':'5.9.3'}},indent=2)+'\n')
env=os.environ.copy();env['PATH']=str(a.node.parent)+os.pathsep+env['PATH']
steps=[]
def run(name,args):
    with (a.out/(name+'.log')).open('w') as log:
        result=subprocess.run(args,cwd=a.out,env=env,stdout=log,stderr=subprocess.STDOUT)
    steps.append({'check':name,'exitCode':result.returncode});print(name,result.returncode,flush=True)
    if result.returncode:raise RuntimeError('Installed check failed: '+name)
run('install',['npm','install','--ignore-scripts','--no-audit','--no-fund'])
shutil.copytree(root/'test',a.out/'test')
run('runtime',[str(a.node),'--test','test/load.test.mjs','test/runtime.test.mjs'])
run('types',[str(a.node),'node_modules/typescript/bin/tsc','--noEmit','--strict','--target','ES2022','--module','NodeNext','--moduleResolution','NodeNext','--lib','ES2022,DOM,ESNext.Disposable','test/types.fixture.ts'])
for name,readme in [('npm-readme',root/'README.md'),('github-readme',root.parent/'README.md')]:
    for index,block in enumerate(re.findall(r'```js\n(.*?)\n```',readme.read_text(),re.S)):
        file=f'{name}-{index}.mjs';(a.out/file).write_text(block+'\n')
        run(f'{name}-{index}',[str(a.node),file])
run('bundled-example',[str(a.node),'node_modules/@arxo/canon-fide-chess/examples/run-arbiter.mjs'])
report={'format':'arxo.fide-chess-installed-check/1','passed':True,
    'node':subprocess.check_output([str(a.node),'--version'],text=True).strip(),
    'tarball':row,'sdk':'0.4.3','engine':'0.5.3','typescript':'5.9.3','skipLibCheck':False,
    'checks':steps,'inventory':inventory,'published':a.registry_install,'releaseVerified':False,'corpus':'not_checked'}
(a.out/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
print('Installed FIDE candidate verified:',report['node'],flush=True)
