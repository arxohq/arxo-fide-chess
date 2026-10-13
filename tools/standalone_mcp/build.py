#!/usr/bin/env python3
"""Build and accept an OCI candidate exclusively from already-acquired inputs."""
import argparse
import hashlib
import json
import os
import re
import shutil
from pathlib import Path
import subprocess
import tempfile
import sys
sys.path.insert(0,str(Path(__file__).parent))
from .identity import image_id, archive_image_id, validate_container_policy
from .config import load as load_config, ref, env_prefix


def run(*command):
    subprocess.run(list(map(str,command)),check=True)


def output(*command):
    return subprocess.check_output(list(map(str,command)),text=True).strip()


def checksum(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()




def build_image(command, iid_path):
    if iid_path.exists():raise ValueError('Build image ID file must be new')
    run(*command[:-1],'--iidfile',iid_path,command[-1])
    return image_id(iid_path.read_text().strip())


def start_pinned_container(command, built_id):
    return output(*command,image_id(built_id))


def save_pinned_image(built_id, path):
    run('docker','save','--output',path,image_id(built_id))
    archive_image_id(path,built_id)


def final_gate(root, out):
    config=load_config(root)
    lock=json.loads(ref(root, config, 'runtimeLock').read_text())
    contract=json.loads(ref(root, config, 'runtimeContract').read_text())
    compatibility=json.loads(ref(root, config, 'hostCompatibility').read_text())
    host=lock['host'];pin=host['platforms']['linux-amd64']
    if not re.fullmatch(r'sha256:[0-9a-f]{64}',pin.get('binarySha256','')):raise ValueError('Final binary SHA-256 pin is invalid')
    source=host.get('sourceCommit')
    if not re.fullmatch(r'[0-9a-f]{40}',source or ''):raise ValueError('Final host source commit is not immutable')
    expected={'platform':'linux-amd64','binarySha256':pin['binarySha256'],'sourceCommit':source}
    if contract.get('status')!='accepted' or contract.get('acceptance',{}).get('finalHostPin')!=expected:raise ValueError('Runtime contract has not accepted the final Linux host')
    platform=compatibility.get('platforms',{}).get('linux-amd64',{})
    if compatibility.get('status')!='compatible' or platform.get('status')!='compatible':raise ValueError('Final Linux compatibility is not proven')
    if not platform.get('checks') or any(c.get('status')!='passed' for c in platform['checks']):raise ValueError('Final Linux compatibility checks are missing or not passed')
    if platform.get('binarySha256')!=expected['binarySha256'] or platform.get('sourceCommit')!=source or pin.get('sourceCommit',source)!=source:raise ValueError('Linux compatibility receipt belongs to another host/source')
    if not ref(root, config, 'treePin').is_file() or ref(root, config, 'treePin').read_bytes()!=(out/'tree.pin.json').read_bytes():raise ValueError('Generated runtime differs from the tracked accepted tree pin')
    if checksum(out/'runtime/bin/law-mcp-server')!=expected['binarySha256'].removeprefix('sha256:'):raise ValueError('Packaged host differs from accepted final host')
    smoke=json.loads((out/'offline-smoke.json').read_text())
    if smoke.get('status')!='passed' or not smoke.get('checks') or any(c.get('status')!='passed' for c in smoke['checks']):raise ValueError('Offline checks are missing or failed')
    if smoke.get('hostSha256')!=expected['binarySha256'].removeprefix('sha256:') or smoke.get('casesSha256')!=checksum(ref(root, config, 'cases')) or smoke.get('sourcePolicySha256')!=checksum(ref(root, config, 'sourcePolicy')):raise ValueError('Offline checks belong to different host/cases/policy')
    if 'network none' not in smoke.get('networkIsolation',''):raise ValueError('Offline checks lack infrastructure network isolation')
    return expected


def reuse_gate(root,out):
    config=load_config(root)
    smoke=json.loads((out/'offline-smoke.json').read_text())
    if smoke['status']!='passed' or not smoke['checks'] or any(c['status']!='passed' for c in smoke['checks']):raise ValueError('Offline receipt is not successful')
    if 'network none' not in smoke['networkIsolation']:raise ValueError('Offline receipt has no enforced network isolation')
    if smoke['hostSha256']!=checksum(out/'runtime/bin/law-mcp-server') or smoke['casesSha256']!=checksum(ref(root, config, 'cases')) or smoke['sourcePolicySha256']!=checksum(ref(root, config, 'sourcePolicy')):raise ValueError('Offline acceptance inputs changed')
    for key, name in [('runtimeLock', 'runtime.lock.json'), ('sourcePolicy', 'source-policy.json'), ('runtimePolicy', 'runtime-policy.json')]:
        if ref(root, config, key).read_bytes()!=(out/'runtime/mcp'/name).read_bytes():raise ValueError('Runtime policy/host lock changed after offline acceptance')
    config=load_config(root)
    profile=json.dumps(json.loads(ref(root, config, 'profile').read_text()),sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()+b'\n'
    if profile!=(out/f'runtime/apps/mcp/profiles/{config["profileId"]}.json').read_bytes():raise ValueError('Profile changed after offline acceptance')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root',type=Path,default=Path('.'))
    ap.add_argument('--acquired',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--source-commit',required=True)
    ap.add_argument('--reuse-offline',action='store_true',help='Reuse independently verified offline output; still apply every final gate')
    ap.add_argument('--image')
    args=ap.parse_args()
    if not re.fullmatch(r'[0-9a-f]{40}',args.source_commit):raise ValueError('Build source must be an exact 40-character Git SHA')
    root=args.root.resolve();acquired=args.acquired.resolve();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    config=load_config(root);prefix=env_prefix(config)
    args.image=args.image or 'arxo-'+config['profileId']+'-mcp:candidate'
    build=json.loads(ref(root, config, 'buildLock').read_text());acq=json.loads((acquired/'acquisition.json').read_text())
    if acq.get('runtimeLockSha256')!=checksum(ref(root, config, 'runtimeLock')) or acq.get('buildLockSha256')!=checksum(ref(root, config, 'buildLock')):raise ValueError('Acquired runtime/build lock inputs changed')
    if not acq.get('imagesAcquired'):raise ValueError('Acquisition did not acquire pinned builder/base images')
    for name in ('builderImage','baseImage'):
        if acq[name]!=build[name]:raise ValueError('Build image acquisition pin changed')
        output('docker','image','inspect',build[name])
    builder=build['builderImage']
    mounts=['--mount',f'type=bind,src={root},dst=/src,readonly','--mount',f'type=bind,src={acquired},dst=/acquired,readonly','--mount',f'type=bind,src={out},dst=/out']
    common=['docker','run','--rm','--platform','linux/amd64','--read-only','--tmpfs','/tmp:rw,noexec,nosuid,size=256m','--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','128','--memory','1g','--user',f'{os.getuid()}:{os.getgid()}']
    if args.reuse_offline:
        reuse_gate(root,out)
        run(*common,'--network','none',*mounts,builder,'python','/src/tools/verify_mcp_runtime.py','--root','/out/runtime','--pin','/src/mcp/tree.pin.json')
        run(*common,'--network','none',*mounts,builder,'python','/src/tools/bundle_mcp.py','--root','/out/runtime','--output','/out/runtime-reverified.tar.gz','--pin','/src/mcp/tree.pin.json')
        if (out/'runtime.tar.gz').read_bytes()!=(out/'runtime-reverified.tar.gz').read_bytes():raise ValueError('Accepted archive differs from the verified packaged tree')
    else:
        run(*common,'--network','none',*mounts,builder,'python','/src/tools/offline_mcp.py','--root','/src','--acquired','/acquired','--output','/out')
    accepted_host=final_gate(root,out)
    for key, name in [('runtimeContract', 'runtime-contract.json'), ('hostCompatibility', 'host-compatibility.json'), ('runtimeLock', 'runtime.lock.json')]:
        shutil.copyfile(ref(root, config, key),out/name)

    context=out/'context-image'
    if context.exists() or context.is_symlink():raise ValueError('Final image context must be new')
    context.mkdir()
    shutil.copytree(out/'runtime',context/'runtime')
    recipe={}
    for source,destination in [('Dockerfile','Dockerfile'),('.dockerignore','.dockerignore'),('NOTICE','NOTICE'),('tools/mcp_entrypoint.sh','mcp_entrypoint.sh')]:
        shutil.copyfile(root/source,context/destination)
        recipe[source]=checksum(root/source)
    run(*common,'--network','none',*mounts,builder,'python','/src/tools/verify_mcp_runtime.py','--root','/out/context-image/runtime','--pin','/src/mcp/tree.pin.json')
    tree=json.loads((out/'tree.pin.json').read_text())
    tree_digest=tree.get('treeDigest',tree.get('digest',tree.get('treeSha256')))
    if not tree_digest:raise ValueError('Tree pin lacks its canonical digest')
    image_id_built=build_image(['docker','build','--platform','linux/amd64','--network','none','--pull=false','--build-arg','BASE_IMAGE='+build['baseImage'],'--build-arg',('CNAF_COMMIT=' if config['legacyCnaf'] else 'SOURCE_COMMIT=')+args.source_commit,'--build-arg','RUNTIME_TREE_DIGEST='+tree_digest,'--tag',args.image,str(context)],out/'built-image.id')
    token='acceptance-token-local-only';origin='https://'+config['profileId']+'-acceptance.invalid'
    container=start_pinned_container(['docker','run','-d','--platform','linux/amd64','--network','none','--read-only','--tmpfs','/state:rw,noexec,nosuid,nodev,size=64m,mode=0700,uid=65532,gid=65532','--tmpfs','/tmp:rw,noexec,nosuid,nodev,size=8m','--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','128','--memory','512m','--cpus','1','-e',prefix+'TOKEN='+token,'-e',prefix+'ALLOWED_ORIGINS='+origin],image_id_built)
    try:
        run(*common,'--network','container:'+container,*mounts,builder,'python','/src/tools/mcp_smoke.py','--url','http://127.0.0.1:8722/mcp','--transport','http','--host','/out/runtime/bin/law-mcp-server','--cases','/src/mcp/cases/acceptance.json','--source-policy','/src/mcp/source-policy.json','--receipt','/out/image-smoke.json','--token',token,'--origin',origin,'--network-evidence','isolated OCI --network none; runner --network container:<id>')
        inspection=json.loads(output('docker','inspect',container))[0]
        policy={'Image':inspection['Image'],'Mounts':inspection['Mounts'],'HostConfig':{k:inspection['HostConfig'][k] for k in ('NetworkMode','ReadonlyRootfs','Privileged','CapDrop','CapAdd','SecurityOpt','Tmpfs','Memory','PidsLimit','NanoCpus')},'Config':{'User':inspection['Config']['User']}}
        validate_container_policy(policy,image_id_built)
        (out/'container-policy.json').write_text(json.dumps(policy,indent=2)+'\n')
    finally:run('docker','rm','-f',container)
    image_id=image_id_built
    save_pinned_image(image_id,out/'image.tar')
    files=['image.tar','runtime.tar.gz','tree.pin.json','offline-smoke.json','image-smoke.json','materialization.json','container-policy.json','runtime-contract.json','host-compatibility.json','runtime.lock.json']
    offline=json.loads((out/'offline-smoke.json').read_text());image_smoke=json.loads((out/'image-smoke.json').read_text())
    acceptance={'casesSha256':offline['casesSha256'],'sourcePolicySha256':offline['sourcePolicySha256'],'httpCheckIds':sorted(c['id'] for c in image_smoke['checks'] if c['id'] not in ('auth-refusal','public-edge-initialize','public-access'))}
    receipt={'acceptance':acceptance,'format':'arxo.mcp-candidate/0.1','profile':config['profileId'],'producer':config['producerRepository'],'sourceCommit':args.source_commit,'imageId':image_id,'imageLocalTag':args.image,'runtimeTreeDigest':tree_digest,'hostBinarySha256':checksum(out/'runtime/bin/law-mcp-server'),'files':{name:checksum(out/name) for name in files},'fullCorpus':'not_checked','releaseVerified':False,'status':'accepted','acceptedHost':accepted_host,'imageRecipeSha256':recipe,'buildLockSha256':checksum(ref(root, config, 'buildLock'))}
    (out/'candidate.json').write_text(json.dumps(receipt,indent=2)+'\n')
    (out/'candidate.json.sha256').write_text(checksum(out/'candidate.json')+'  candidate.json\n')
    print(json.dumps({'status':'accepted','imageId':image_id,'candidateReceiptSha256':checksum(out/'candidate.json')}))


if __name__=='__main__':main()
