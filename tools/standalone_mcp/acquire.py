#!/usr/bin/env python3
"""Online-only acquisition of immutable host and builder/runtime images."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile
import urllib.request
from .config import load as load_config, ref, read_json
from .materialize import validate_runtime_lock


def sha(data):
    return hashlib.sha256(data).hexdigest()


def acquire(root, output, platform, pull_images=True):
    config = load_config(root)
    lock = read_json(ref(root, config, 'runtimeLock'));validate_runtime_lock(lock)
    build = read_json(ref(root, config, 'buildLock'))
    pin = lock['host']['platforms'][platform]
    url = pin['url']
    if not url.startswith('https://') or not re.fullmatch(r'[0-9a-f]{64}', pin['archiveSha256'].removeprefix('sha256:')):
        raise ValueError('Host acquisition needs HTTPS and an exact SHA-256')
    if output.is_symlink() or output.exists():
        raise ValueError('Acquisition output must be a new real directory')
    output.mkdir(parents=True)
    archive = output / 'host.tgz'
    with urllib.request.urlopen(url, timeout=60) as response:
        data = response.read(128*1024*1024+1)
    if len(data)>128*1024*1024:
        raise ValueError('Pinned host archive exceeds the acquisition size bound')
    if sha(data) != pin['archiveSha256'].removeprefix('sha256:'):
        raise ValueError('Host archive SHA-256 mismatch')
    archive.write_bytes(data)
    with tarfile.open(archive) as tgz:
        name = str(PurePosixPath(pin['binaryPath']))
        if PurePosixPath(name).is_absolute() or '..' in PurePosixPath(name).parts:
            raise ValueError('Unsafe binary path')
        members = [m for m in tgz.getmembers() if m.name == name]
        if len(members) != 1 or not members[0].isfile():
            raise ValueError('Pinned binary must be a unique regular archive member')
        data = tgz.extractfile(members[0]).read()
    if sha(data) != pin['binarySha256'].removeprefix('sha256:'):
        raise ValueError('Host binary SHA-256 mismatch')
    binary = output / 'law-mcp-server'
    binary.write_bytes(data)
    binary.chmod(0o555)
    for image in (build['builderImage'], build['baseImage']):
        if not re.search(r'@sha256:[0-9a-f]{64}$', image):
            raise ValueError('Image must have an exact digest')
        if pull_images:
            subprocess.run(['docker', 'pull', '--platform', 'linux/amd64', image], check=True)
    receipt = {'format': 'arxo.mcp-acquisition/0.1', 'platform': platform,
               'archiveSha256': sha(archive.read_bytes()), 'binarySha256': sha(binary.read_bytes()),
               'runtimeLockSha256': sha(ref(root, config, 'runtimeLock').read_bytes()),
               'buildLockSha256': sha(ref(root, config, 'buildLock').read_bytes()),
               'builderImage': build['builderImage'], 'baseImage': build['baseImage'],
               'imagesAcquired': pull_images}
    (output/'acquisition.json').write_text(json.dumps(receipt, indent=2)+'\n')
    return receipt


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', type=Path, default=Path('.'))
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--platform', default='linux-amd64')
    ap.add_argument('--no-images', action='store_true', help='Host-only diagnostics; not an offline build prerequisite')
    args = ap.parse_args()
    print(json.dumps(acquire(args.root.resolve(), args.output.resolve(), args.platform, not args.no_images)))


if __name__ == '__main__':
    main()
