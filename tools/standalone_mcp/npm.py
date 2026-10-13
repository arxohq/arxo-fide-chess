#!/usr/bin/env python3
"""Package an accepted runtime for npm; smoke a clean installed stdio consumer.

No model compilation, source fetch or publishing is performed by this tool.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import queue
import shutil
import subprocess
import tarfile
import tempfile
import threading
import time

from .verify import canonical, sha256, verify
from .smoke import exercise
from .config import load as load_config, read_json, ref

ROOT = Path(__file__).resolve().parents[2]
SHARED_MODULES = ('__init__', 'config', 'materialize', 'verify', 'bundle', 'acquire', 'build', 'offline', 'identity', 'source_policy', 'smoke', 'npm', 'promote')

def source_files(root):
    config = load_config(root)
    if config['legacyCnaf']:
        return ('tools/mcp_npm.py', 'tools/mcp_smoke.py', 'tools/verify_mcp_runtime.py', 'mcp/cases/acceptance.json', 'mcp/source-policy.json', 'mcp/tree.pin.json')
    return ('tools/mcp_npm.py', 'tools/mcp_smoke.py', 'tools/verify_mcp_runtime.py', 'mcp/delivery.json', 'mcp/npm/bin/arxo-mcp.cjs', config['refs']['cases'], config['refs']['sourcePolicy'], config['refs']['treePin'], *('tools/standalone_mcp/' + name + '.py' for name in SHARED_MODULES))

HOST_OS = {'linux-x64': ('linux', 'x64'), 'darwin-arm64': ('darwin', 'arm64')}


def dump(path, value):
    path.write_bytes(canonical(value) + b'\n')


def archive_runtime(archive, out, expected):
    if sha256(archive.read_bytes()) != expected:
        raise ValueError('runtime archive differs from the accepted OCI archive pin')
    with tarfile.open(archive, 'r:gz') as tar:
        seen = set()
        for row in tar.getmembers():
            p = PurePosixPath(row.name)
            if not p.parts or p.parts[0] != 'runtime' or p.is_absolute() or '..' in p.parts or '\\' in row.name or row.name in seen or not (row.isdir() or row.isfile()):
                raise ValueError('unsafe or duplicate runtime archive entry')
            seen.add(row.name)
        tar.extractall(out, filter='data')
    return out / 'runtime'


def pack(root, archive, binaries, out, commit, host_archives=None):
    config = load_config(root)
    wrapper_name = config["packageName"]
    profile = read_json(ref(root, config, "profile"))
    accepted_sources = source_files(root)
    if profile.get("name") != config["profileId"]:
        raise ValueError("npm profile differs from delivery config")
    host_archives = host_archives or {}
    if out.exists():
        raise ValueError('npm output must be a new directory')
    inputs = json.loads((root / 'mcp/npm/host-pins.json').read_bytes())
    meta = json.loads((root / 'mcp/npm/package.json').read_bytes())
    original_pin = read_json(ref(root, config, 'treePin'))
    if meta.get('name') != wrapper_name or inputs.get('profile') != config['profileId'] and not config['legacyCnaf']:
        raise ValueError('npm package/profile identity differs from delivery config')
    if original_pin['treeSha256'] != inputs['runtime']['treeSha256']:
        raise ValueError('npm runtime pin differs from accepted tree')
    if set(binaries) != set(inputs['platforms']):
        raise ValueError('every declared platform needs its exact binary')
    for key, row in inputs['platforms'].items():
        if key not in HOST_OS or sha256(binaries[key].read_bytes()) != row['sha256']:
            raise ValueError('shared host binary differs from platform pin: ' + key)
        if meta['optionalDependencies'].get(row['package']) != inputs['hostVersion']:
            raise ValueError('optional host dependency is not exactly pinned')
    if set(meta['optionalDependencies']) != {p['package'] for p in inputs['platforms'].values()}:
        raise ValueError('unsupported optional host dependency')
    with tempfile.TemporaryDirectory(prefix=config['profileId']+'-npm-input-') as tmp:
        runtime = archive_runtime(archive, Path(tmp), inputs['runtime']['archiveSha256'])
        verify(runtime, ref(root, config, 'treePin'))
        out.mkdir(parents=True)
        packages = out / 'packages'; tarballs = out / 'tarballs'; tarballs.mkdir()
        wrapper = packages / wrapper_name.split('/')[-1]; wrapper.mkdir(parents=True)
        data_entries = [r for r in original_pin['entries'] if r['path'] not in ('bin', 'bin/law-mcp-server')]
        for row in data_entries:
            target = wrapper / 'slice' / row['path']
            if row['type'] == 'directory':
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(runtime / row['path'], target)
                target.chmod(0o644)
        pin = {'format': 'cnaf.mcp-npm-pin/1' if config['legacyCnaf'] else 'arxo.mcp-npm-pin/0.1', 'profile': config['profileId'], 'serverName': profile['serverName'],
               'runtime': inputs['runtime'], 'hostSourceCommit': inputs['hostSourceCommit'],
               'data': {'algorithm': original_pin['algorithm'], 'treeSha256': sha256(canonical(data_entries)), 'entries': data_entries},
               'binaries': {k: {**v, 'version': inputs['hostVersion']} for k,v in inputs['platforms'].items()},
               'fullCorpus': 'not_checked', 'releaseVerified': False}
        dump(wrapper / 'pin.json', pin)
        (wrapper / 'bin').mkdir()
        launcher = (root / 'mcp/npm/bin/arxo-mcp.cjs').read_text().replace('__PIN_SHA256__', sha256((wrapper / 'pin.json').read_bytes()))
        (wrapper / 'bin/arxo-mcp.cjs').write_text(launcher); (wrapper / 'bin/arxo-mcp.cjs').chmod(0o755)
        dump(wrapper / 'package.json', meta)
        for name in ('LICENSE', 'NOTICE'):
            shutil.copyfile(runtime / name, wrapper / name)
        shutil.copyfile(root / 'mcp/npm/README.md', wrapper / 'README.md')
        rows = []
        if not config['legacyCnaf']:
            if set(host_archives) != set(inputs['platforms']):
                raise ValueError('Generic packaging needs exact published host archives')
            for key, host in inputs['platforms'].items():
                original = host_archives[key]
                raw = original.read_bytes()
                if sha256(raw) != host['archiveSha256'] or len(raw) != host['bytes']:
                    raise ValueError('Published host archive identity differs: ' + key)
                with tarfile.open(original, 'r:gz') as tar:
                    members = tar.getmembers()
                    for member in members:
                        path = PurePosixPath(member.name)
                        if not path.parts or path.parts[0] != 'package' or path.is_absolute() or '..' in path.parts or '\\' in member.name or not (member.isdir() or member.isfile()):
                            raise ValueError('Unsafe host archive entry')
                    def member_bytes(name):
                        matches = [m for m in members if m.name == name]
                        if len(matches) != 1 or not matches[0].isfile():
                            raise ValueError('Missing/ambiguous host archive member: ' + name)
                        return tar.extractfile(matches[0]).read()
                    declared = json.loads(member_bytes('package/package.json'))
                    if declared['name'] != host['package'] or declared['version'] != inputs['hostVersion'] or declared.get('scripts') or declared.get('dependencies'):
                        raise ValueError('Published host package metadata differs or has forbidden execution dependencies')
                    if sha256(member_bytes('package/bin/law-mcp-server')) != host['sha256']:
                        raise ValueError('Published host archive binary differs')
                filename = host['package'].replace('@', '').replace('/', '-') + '-' + inputs['hostVersion'] + '.tgz'
                shutil.copyfile(original, tarballs / filename)
                rows.append({'name': host['package'], 'version': inputs['hostVersion'], 'tarball': filename,
                             'sha256': sha256(raw), 'bytes': len(raw), 'distTag': host['distTag']})
        for key, host in inputs['platforms'].items() if config['legacyCnaf'] else ():

            directory = packages / ('mcp-host-' + key); (directory / 'bin').mkdir(parents=True)
            shutil.copyfile(binaries[key], directory / 'bin/law-mcp-server'); (directory / 'bin/law-mcp-server').chmod(0o755)
            shutil.copyfile(runtime / 'notices/LICENSE.host', directory / 'LICENSE')
            shutil.copyfile(runtime / 'notices/host.NOTICE', directory / 'NOTICE')
            dump(directory / 'package.json', {'name': host['package'], 'version': inputs['hostVersion'],
                'description': 'Shared Arxo MCP host for ' + key, 'license': 'Apache-2.0',
                'os': [HOST_OS[key][0]], 'cpu': [HOST_OS[key][1]], 'files': ['bin/law-mcp-server', 'LICENSE', 'NOTICE', 'README.md'],
                'repository': {'type': 'git', 'url': 'https://github.com/arxohq/law-archive.git'},
                'publishConfig': {'access': 'public', 'tag': 'cnaf-preview'}})
            (directory / 'README.md').write_text('# ' + host['package'] + '\n\nShared native Arxo MCP host. Install `@arxo/mcp-cnaf`, which pins this optional dependency.\n\nSource: https://github.com/arxohq/law-archive/commit/' + inputs['hostSourceCommit'] + '\n\nThis preview adds strict caller-context handling to the common host; it contains no CNAF data. The stable host tag is unchanged.\n')
            rows.append(npm_pack(directory, tarballs, 'cnaf-preview'))
        rows.append(npm_pack(wrapper, tarballs, 'latest'))
        release = {'schema': 'arxo.mcp-npm-release/1', 'profile': config['profileId'], 'registry': 'https://registry.npmjs.org',
                   'packages': rows, 'pin': pin,
                   'consumer': {'repository': config['producerRepository'], 'commit': commit,
                                'files': {p: sha256((root / p).read_bytes()) for p in accepted_sources}},
                   'fullCorpus': 'not_checked', 'releaseVerified': False}
        dump(out / 'npm-release.json', release)
        print(json.dumps({'packages': [{k:r[k] for k in ('name','version','sha256','bytes')} for r in rows],
                          'dataTreeSha256': pin['data']['treeSha256'], 'runtimeTreeSha256': pin['runtime']['treeSha256']}))
        return release


def npm_pack(directory, out, tag):
    done = subprocess.run(['npm','pack','--ignore-scripts','--json','--pack-destination',str(out)], cwd=directory, capture_output=True, text=True, check=True)
    row = json.loads(done.stdout)[0]; target = out / row['filename']
    return {'name': row['name'], 'version': row['version'], 'tarball': row['filename'],
            'sha256': sha256(target.read_bytes()), 'bytes': target.stat().st_size, 'distTag': tag}


class Launcher:
    def __init__(self, command, cwd, env):
        self.proc = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.lines = queue.Queue(); self.errors = []
        def reader():
            for line in self.proc.stdout: self.lines.put(line)
            self.lines.put(None)
        def errors():
            for line in self.proc.stderr: self.errors.append(line)
        threading.Thread(target=reader, daemon=True).start(); threading.Thread(target=errors, daemon=True).start()
    def call(self, request):
        self.proc.stdin.write(json.dumps(request)+'\n'); self.proc.stdin.flush()
        line = self.lines.get(timeout=60)
        if line is None: raise ValueError('stdio launcher exited: '+''.join(self.errors[-5:]))
        reply = json.loads(line)
        if reply.get('id') != request['id']: raise ValueError('stdio response ID differs')
        return reply
    def notify(self, method):
        self.proc.stdin.write(json.dumps({'jsonrpc':'2.0','method':method})+'\n'); self.proc.stdin.flush()
    def close(self):
        self.proc.stdin.close()
        try: self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.terminate()
            try: self.proc.wait(timeout=7)
            except subprocess.TimeoutExpired: self.proc.kill(); self.proc.wait()
        if self.proc.returncode != 0: raise ValueError('stdio process exit '+str(self.proc.returncode))


def smoke(directory, registry, receipt, npx=False):
    release = read_json(directory / 'npm-release.json')
    config = load_config(ROOT)
    accepted_sources = source_files(ROOT)
    wrapper_name = config['packageName']
    if release['profile'] != config['profileId'] or release['consumer']['repository'] != config['producerRepository']:
        raise ValueError('Consumer identity differs from delivery config')
    if set(release['consumer']['files']) != set(accepted_sources): raise ValueError('unexpected consumer acceptance files')
    for rel in accepted_sources:
        if sha256((ROOT/rel).read_bytes()) != release['consumer']['files'][rel]: raise ValueError('consumer acceptance source differs: '+rel)
    key = {'Darwin':'darwin','Linux':'linux'}.get(platform.system(),'unknown') + '-' + {'arm64':'arm64','aarch64':'arm64','x86_64':'x64'}.get(platform.machine(),platform.machine())
    host = release['pin']['binaries'][key]
    selected = [r for r in release['packages'] if r['name'] in (host['package'],wrapper_name)]
    if len(selected) != 2 or selected[-1]['name'] != wrapper_name: raise ValueError('candidate order/package set differs')
    for row in release['packages']:
        if sha256((directory / 'tarballs' / row['tarball']).read_bytes()) != row['sha256']: raise ValueError('candidate tarball mismatch')
    with tempfile.TemporaryDirectory(prefix=config['profileId']+'-npm-consumer-') as tmp:
        consumer = Path(tmp); (consumer / 'package.json').write_text('{"name":"consumer","private":true}\n')
        for p in ('.npmrc','.npm-globalrc'): (consumer / p).write_text('')
        env = {'PATH':os.environ['PATH'], 'HOME':str(consumer), 'TMPDIR':str(consumer),
               'NPM_CONFIG_USERCONFIG':str(consumer/'.npmrc'),'NPM_CONFIG_GLOBALCONFIG':str(consumer/'.npm-globalrc'),
               'NPM_CONFIG_CACHE':str(consumer/'.npm-cache'),'NPM_CONFIG_REGISTRY':release['registry']}
        specs = [r['name']+'@'+r['version'] for r in selected] if registry else [str(directory/'tarballs'/r['tarball']) for r in selected]
        subprocess.run(['npm','install','--ignore-scripts','--no-audit','--no-fund',*specs], cwd=consumer, env=env, capture_output=True, text=True, check=True, timeout=180)
        installed = consumer / 'node_modules' / wrapper_name
        # npm metadata or a matching pin alone cannot identify the published
        # launcher. Compare every installed package file with its frozen archive.
        for row in selected:
            verify_installed(consumer / 'node_modules' / row['name'], directory / 'tarballs' / row['tarball'])
        if (installed / 'pin.json').read_bytes() != canonical(release['pin'])+b'\n': raise ValueError('installed pin differs from candidate')
        host_binary = consumer / 'node_modules' / host['package'] / 'bin/law-mcp-server'
        if sha256(host_binary.read_bytes()) != host['sha256']: raise ValueError('installed native host differs')
        meta = read_json(installed / 'package.json')
        if not isinstance(meta.get('bin'), dict) or len(meta['bin']) != 1:
            raise ValueError('Standalone wrapper must declare one launcher')
        bin_name = next(iter(meta['bin']))
        command = ['npx', '--offline', '--yes', bin_name] if npx else [str(consumer/'node_modules/.bin'/bin_name)]
        checks=[]; client=Launcher(command,consumer,env); started=time.monotonic()
        try:
            doc=read_json(ref(ROOT, config, 'cases'))
            exercise(client,doc['cases'],host['sha256'].removeprefix('sha256:'),checks,'npx' if npx else 'stdio-installed',read_json(ref(ROOT, config, 'sourcePolicy')),doc['catalogExpectedKeys'],doc.get('referenceRequests', []))
        finally:client.close()
        if list(consumer.glob(release['pin']['serverName']+'-*')): raise ValueError('launcher temporary state was not removed')
        result={'format':'cnaf.mcp-npm-smoke/1' if config['legacyCnaf'] else 'arxo.mcp-npm-smoke/0.1','status':'passed' if all(r['status']=='passed' for r in checks) else 'failed',
                'platform':key,'registryInstall':registry,'npx':npx,'elapsedSeconds':round(time.monotonic()-started,3),
                'hostSha256':host['sha256'],'runtimeTreeSha256':release['pin']['runtime']['treeSha256'],
                'dataTreeSha256':release['pin']['data']['treeSha256'],'checks':checks,'stateCleanup':'passed',
                'consumerCommit':release['consumer']['commit'], 'sourceFiles':release['consumer']['files'],
                'fullCorpus':'not_checked','releaseVerified':False}
        receipt.parent.mkdir(parents=True,exist_ok=True); dump(receipt,result)
        if result['status']!='passed': raise ValueError('installed subject smoke failed')
        print(json.dumps({k:result[k] for k in ('status','platform','registryInstall','npx','stateCleanup')} | {'checks':len(checks)}))


def verify_installed(installed, archive):
    expected = {}
    with tarfile.open(archive,'r:gz') as tar:
        for member in tar.getmembers():
            p=PurePosixPath(member.name)
            if not p.parts or p.parts[0]!='package' or p.is_absolute() or '..' in p.parts or '\\' in member.name or not (member.isdir() or member.isfile()):
                raise ValueError('unsafe npm archive entry')
            if member.isfile():
                rel=p.relative_to('package').as_posix()
                if rel in expected:raise ValueError('duplicate npm archive file')
                expected[rel]=sha256(tar.extractfile(member).read())
    observed={}
    for p in installed.rglob('*'):
        if p.is_symlink():raise ValueError('unexpected installed symlink')
        if p.is_file():observed[p.relative_to(installed).as_posix()]=sha256(p.read_bytes())
    if observed!=expected:raise ValueError('installed package differs from frozen npm archive: '+str(installed.name))


def main():
    ap=argparse.ArgumentParser(description=__doc__); sub=ap.add_subparsers(dest='command',required=True)
    p=sub.add_parser('pack'); p.add_argument('--root',type=Path,default=ROOT); p.add_argument('--runtime-archive',type=Path,required=True); p.add_argument('--binary',action='append',default=[]);p.add_argument('--host-archive',action='append',default=[]); p.add_argument('--out',type=Path,required=True);p.add_argument('--source-commit',required=True)
    p=sub.add_parser('smoke');p.add_argument('directory',type=Path);p.add_argument('--registry',action='store_true');p.add_argument('--npx',action='store_true');p.add_argument('--receipt',type=Path,required=True)
    a=ap.parse_args()
    if a.command=='pack':
        binaries={}
        for item in a.binary:
            key,value=item.split('=',1)
            if key in binaries: raise ValueError('duplicate platform binary')
            binaries[key]=Path(value).resolve()
        host_archives={}
        for item in a.host_archive:
            key,value=item.split('=',1)
            if key in host_archives: raise ValueError('duplicate platform archive')
            host_archives[key]=Path(value).resolve()
        pack(a.root.resolve(),a.runtime_archive.resolve(),binaries,a.out.resolve(),a.source_commit,host_archives)
    else:smoke(a.directory.resolve(),a.registry,a.receipt.resolve(),a.npx)


if __name__=='__main__':main()
