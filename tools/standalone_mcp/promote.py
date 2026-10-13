#!/usr/bin/env python3
"""Promote the exact accepted Docker archive; no materialization or rebuild."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).parent))
from .identity import archive_image_id, validate_container_policy, validate_registry_manifest


from .config import load as load_config, read_json, ref

ROOT=Path(__file__).resolve().parents[2]


def sha(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file():raise ValueError('Artifact must be a real regular file: '+str(path))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(directory, expected_receipt, expected_commit, root=ROOT):
    directory=Path(directory).absolute();root=Path(root).absolute()
    config=load_config(root)
    if directory.is_symlink() or not directory.is_dir():raise ValueError('Candidate directory must be real')
    if not re.fullmatch(r'[0-9a-f]{40}',expected_commit):raise ValueError('Source must be an immutable Git commit')
    receipt_path=directory/'candidate.json'
    if not re.fullmatch(r'[0-9a-f]{64}',expected_receipt) or sha(receipt_path)!=expected_receipt:raise ValueError('Accepted candidate receipt SHA mismatch')
    receipt=read_json(receipt_path)
    if receipt.get('format')!='arxo.mcp-candidate/0.1':raise ValueError('Unsupported accepted candidate format')
    if not config['legacyCnaf'] and (receipt.get('profile')!=config['profileId'] or receipt.get('producer')!=config['producerRepository']):raise ValueError('Accepted candidate belongs to another profile/producer')
    if receipt['status']!='accepted' or receipt['sourceCommit']!=expected_commit:raise ValueError('Candidate was not accepted for the selected immutable commit')
    if receipt['fullCorpus']!='not_checked' or receipt['releaseVerified'] is not False:raise ValueError('Preview acceptance scope changed')
    for name,digest in receipt['files'].items():
        if Path(name).name!=name or name in ('','.', '..') or not re.fullmatch(r'[0-9a-f]{64}',digest):raise ValueError('Unsafe receipt file path/hash')
        if sha(directory/name)!=digest:raise ValueError('Accepted artifact changed: '+name)
    required={'image.tar','runtime.tar.gz','tree.pin.json','offline-smoke.json','image-smoke.json','materialization.json','container-policy.json','runtime-contract.json','host-compatibility.json','runtime.lock.json'}
    if not required<=receipt['files'].keys():raise ValueError('Candidate does not bind all required evidence')
    archive_image_id(directory/'image.tar',receipt['imageId'])
    validate_container_policy(json.loads((directory/'container-policy.json').read_text()),receipt['imageId'])
    lock=json.loads((directory/'runtime.lock.json').read_text())
    contract=json.loads((directory/'runtime-contract.json').read_text())
    compatible=json.loads((directory/'host-compatibility.json').read_text())
    accepted=receipt.get('acceptedHost')
    expected={'platform':'linux-amd64','binarySha256':lock['host']['platforms']['linux-amd64']['binarySha256'],'sourceCommit':lock['host']['sourceCommit']}
    if not re.fullmatch(r'sha256:[0-9a-f]{64}',expected['binarySha256']):raise ValueError('Final binary SHA-256 pin is invalid')
    if not re.fullmatch(r'[0-9a-f]{40}',expected['sourceCommit'] or ''):raise ValueError('Final host source is not an immutable commit')
    if accepted!=expected or contract.get('status')!='accepted' or contract.get('acceptance',{}).get('finalHostPin')!=expected:raise ValueError('Final host/runtime contract identity mismatch')
    linux=compatible.get('platforms',{}).get('linux-amd64',{})
    if compatible.get('status')!='compatible' or linux.get('status')!='compatible' or linux.get('binarySha256')!=expected['binarySha256'] or linux.get('sourceCommit')!=expected['sourceCommit']:raise ValueError('Released host lacks accepted Linux compatibility')
    if not linux.get('checks') or any(c.get('status')!='passed' for c in linux['checks']):raise ValueError('Final Linux compatibility checks are missing or failed')
    if receipt['hostBinarySha256']!=expected['binarySha256'].removeprefix('sha256:'):raise ValueError('Candidate host differs from final release pin')
    if json.loads((directory/'tree.pin.json').read_text())['treeSha256']!=receipt['runtimeTreeDigest']:raise ValueError('Candidate tree pin identity mismatch')
    for name in ('offline-smoke.json','image-smoke.json'):
        smoke=json.loads((directory/name).read_text())
        if smoke['status']!='passed' or smoke['hostSha256']!=receipt['hostBinarySha256']:raise ValueError('Smoke receipt does not accept this host')
        if not smoke['checks'] or any(c['status']!='passed' for c in smoke['checks']):raise ValueError('Smoke has missing or failed checks')
        if 'network none' not in smoke['networkIsolation']:raise ValueError('Offline acceptance has no network-isolation evidence')
    if not config['legacyCnaf']:
        for name,key in [('runtime.lock.json','runtimeLock'),('tree.pin.json','treePin')]:
            if sha(directory/name)!=sha(ref(root,config,key)):raise ValueError('Candidate differs from committed '+key)
    offline=json.loads((directory/'offline-smoke.json').read_text());image=json.loads((directory/'image-smoke.json').read_text())
    expected_acceptance={'casesSha256':offline['casesSha256'],'sourcePolicySha256':offline['sourcePolicySha256'],'httpCheckIds':sorted(c['id'] for c in image['checks'] if c['id'] not in ('auth-refusal','public-edge-initialize','public-access'))}
    if receipt.get('acceptance')!=expected_acceptance or image['casesSha256']!=expected_acceptance['casesSha256'] or image['sourcePolicySha256']!=expected_acceptance['sourcePolicySha256']:raise ValueError('Candidate staging acceptance contract does not bind actual full smoke inputs/checks')
    if not config['legacyCnaf']:
        if expected_acceptance['casesSha256']!=sha(ref(root,config,'cases')) or expected_acceptance['sourcePolicySha256']!=sha(ref(root,config,'sourcePolicy')):
            raise ValueError('Candidate cases/policy differ from committed producer inputs')
    if len(set(expected_acceptance['httpCheckIds']))!=len(expected_acceptance['httpCheckIds']):raise ValueError('Candidate image smoke check IDs are duplicated')
    return receipt


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root',type=Path,default=ROOT)
    ap.add_argument('--directory',type=Path,required=True)
    ap.add_argument('--receipt-sha256',required=True)
    ap.add_argument('--source-commit',required=True)
    ap.add_argument('--image',required=True,help='Destination immutable preview tag')
    args=ap.parse_args()
    config=load_config(args.root)
    receipt=verify(args.directory,args.receipt_sha256,args.source_commit,args.root)
    if not re.fullmatch(r'ghcr\.io/[a-z0-9-]+/[a-z0-9-]+:preview-[0-9a-f]{40}',args.image):raise ValueError('Destination must use preview-<full Git SHA>')
    if args.image!='ghcr.io/'+config['producerRepository']+'-mcp:preview-'+args.source_commit:
        raise ValueError('Destination repository/tag differs from accepted producer and commit')
    existing=subprocess.run(['docker','manifest','inspect',args.image],capture_output=True,text=True)
    if existing.returncode==0:raise ValueError('Immutable image tag already exists; refusing overwrite')
    # An authentication/network failure must not be mistaken for an absent tag.
    if not any(s in existing.stderr.lower() for s in ('manifest unknown','no such manifest','not found')):raise ValueError('Could not establish destination tag absence: '+existing.stderr[:300])
    subprocess.run(['docker','load','--input',str(args.directory/'image.tar')],check=True)
    loaded=subprocess.check_output(['docker','image','inspect','--format','{{.Id}}',receipt['imageId']],text=True).strip()
    if loaded!=receipt['imageId']:raise ValueError('Loaded image identity differs from accepted image')
    subprocess.run(['docker','tag',receipt['imageId'],args.image],check=True)
    subprocess.run(['docker','push',args.image],check=True)
    inspection=json.loads(subprocess.check_output(['docker','image','inspect',args.image],text=True))[0]
    if inspection.get('Id')!=receipt['imageId']:raise ValueError('Pushed local tag no longer identifies the accepted image')
    digests=[d for d in inspection['RepoDigests'] if d.split('@')[0]==args.image.split(':')[0]]
    if len(digests)!=1:raise ValueError('Push did not yield exactly one registry image digest')
    registry_manifest=json.loads(subprocess.check_output(['docker','manifest','inspect',digests[0]],text=True))
    validate_registry_manifest(registry_manifest,receipt['imageId'])
    release={'format':'arxo.mcp-release/0.1','profile':config['profileId'],'producer':config['producerRepository'],'sourceCommit':args.source_commit,'acceptedReceiptSha256':args.receipt_sha256,'image':digests[0],'imageId':receipt['imageId'],'runtimeTreeDigest':receipt['runtimeTreeDigest'],'hostBinarySha256':receipt['hostBinarySha256'],'fullCorpus':'not_checked','releaseVerified':False}
    path=args.directory/'release.json';path.write_text(json.dumps(release,indent=2)+'\n')
    (args.directory/'release.json.sha256').write_text(sha(path)+'  release.json\n')
    print(json.dumps(release))


if __name__=='__main__':main()
