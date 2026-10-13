#!/usr/bin/env python3
"""Offline data build. Run inside the pinned builder with --network none."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from .config import load as load_config, ref


def call(*argv):
    subprocess.run([sys.executable, *map(str, argv)], check=True)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--diagnostic',action='store_true',help='Bootstrap compatibility probe; does not accept an OCI candidate or release')
    ap.add_argument('--root',type=Path,required=True)
    ap.add_argument('--acquired',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    root=args.root.resolve();out=args.output.resolve();host=args.acquired.resolve()/'law-mcp-server'
    config=load_config(root)
    lock=json.loads(ref(root, config, 'runtimeLock').read_text())
    expected=lock['host']['platforms']['linux-amd64']['binarySha256'].removeprefix('sha256:')
    if hashlib.sha256(host.read_bytes()).hexdigest()!=expected:raise ValueError('Acquired host SHA mismatch')
    build=json.loads(ref(root, config, 'buildLock').read_text())
    expected_python=tuple(int(n) for n in build['python'].split('.'))
    if sys.version_info[:3]!=expected_python:raise ValueError('Offline builder must use pinned Python '+build['python'])
    for name in ('runtime','runtime-second','context'):
        if (out/name).exists():raise ValueError('Build needs a new empty output: '+str(out/name))
    call('-m','unittest','discover','-s',root/'tests/mcp','-p','test_*.py')
    for suffix in ('','-second'):
        call(root/'tools/materialize_mcp.py','--root',root,'--output',out/('runtime'+suffix),'--host',host,'--platform','linux-amd64','--tree-pin',out/('tree'+suffix+'.pin.json'),'--receipt',out/('materialization'+suffix+'.json'))
        call(root/'tools/verify_mcp_runtime.py','--root',out/('runtime'+suffix),'--pin',out/('tree'+suffix+'.pin.json'))
        call(root/'tools/bundle_mcp.py','--root',out/('runtime'+suffix),'--output',out/('runtime'+suffix+'.tar.gz'),'--pin',out/('tree'+suffix+'.pin.json'))
    if (out/'tree.pin.json').read_bytes()!=(out/'tree-second.pin.json').read_bytes():raise ValueError('Independent runtime trees differ')
    if (out/'runtime.tar.gz').read_bytes()!=(out/'runtime-second.tar.gz').read_bytes():raise ValueError('Independent normalized runtime archives differ')
    call(root/'tools/mcp_smoke.py','--root',out/'runtime','--host',out/'runtime/bin/law-mcp-server','--cases',ref(root, config, 'cases'),'--source-policy',ref(root, config, 'sourcePolicy'),'--receipt',out/'offline-smoke.json','--network-evidence','docker --network none; no law-dsl mount')
    context=out/'context';context.mkdir()
    shutil.copytree(out/'runtime',context/'runtime')
    for source,destination in [('Dockerfile','Dockerfile'),('.dockerignore','.dockerignore'),('NOTICE','NOTICE'),('tools/mcp_entrypoint.sh','mcp_entrypoint.sh')]:shutil.copyfile(root/source,context/destination)
    print(json.dumps({'status':'diagnostic' if args.diagnostic else 'offline_checks_passed','releaseEligible':False,'output':str(out),'deterministicTrees':True,'deterministicArchives':True}))


if __name__=='__main__':main()
