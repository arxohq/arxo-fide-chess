#!/usr/bin/env python3
"""Independent, offline raw-byte runtime inventory verifier (stdlib only).

Does not import the materializer or infer expected files from the runtime itself.
A trusted, external tree pin is required. Timestamps are deliberately excluded.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()


def sha256(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def verify(root, pin_path):
    root, pin_path = Path(root).absolute(), Path(pin_path).absolute()
    if root.is_symlink() or not root.is_dir():
        raise ValueError('runtime root must be a real directory')
    if pin_path.is_relative_to(root) or pin_path.is_symlink():
        raise ValueError('trusted pin must be external and not a symlink')
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError(f'duplicate pin JSON field: {key}')
            value[key] = item
        return value
    pin = json.loads(pin_path.read_bytes(), object_pairs_hook=unique)
    if pin.get('format') != 'arxo.mcp-tree-pin/0.1' or pin.get('algorithm') != 'sha256-canonical-inventory-v1':
        raise ValueError('unsupported tree pin format/algorithm')
    entries = pin['entries']
    expected = {}
    for row in entries:
        rel = row['path']
        p = PurePosixPath(rel)
        if not rel or p.is_absolute() or '\\' in rel or any(v in ('', '.', '..') for v in rel.split('/')):
            raise ValueError(f'invalid pinned path: {rel}')
        if rel in expected:
            raise ValueError(f'duplicate pinned path: {rel}')
        if row['type'] not in ('directory', 'file') or row['mode'] not in ('0644', '0755'):
            raise ValueError(f'invalid pinned entry type/mode: {rel}')
        want_mode = '0755' if row['type'] == 'directory' or rel == 'bin/law-mcp-server' else '0644'
        if row['mode'] != want_mode:
            raise ValueError(f'noncanonical pinned mode: {rel}')
        if row['type'] == 'file' and (type(row['size']) is not int or row['size'] < 0):
            raise ValueError(f'invalid pinned byte size: {rel}')
        fields = {'path', 'mode', 'type'} | ({'size', 'sha256'} if row['type'] == 'file' else set())
        if set(row) != fields:
            raise ValueError(f'invalid pinned entry fields: {rel}')
        expected[rel] = row
    if list(expected) != sorted(expected) or sha256(canonical(entries)) != pin['treeSha256']:
        raise ValueError('pin inventory ordering/digest mismatch')
    observed = set()
    for path in sorted(root.rglob('*'), key=lambda path: path.relative_to(root).as_posix()):
        rel = path.relative_to(root).as_posix(); observed.add(rel)
        if rel not in expected:
            raise ValueError(f'extra runtime entry: {rel}')
        row = expected[rel]; mode = path.lstat().st_mode
        if not (stat.S_ISREG(mode) if row['type'] == 'file' else stat.S_ISDIR(mode)):
            raise ValueError(f'wrong runtime file type: {rel}')
        if stat.S_IMODE(mode) != int(row['mode'], 8):
            raise ValueError(f'wrong runtime mode: {rel}')
        if row['type'] == 'file':
            raw = path.read_bytes()
            if len(raw) != row['size'] or sha256(raw) != row['sha256']:
                raise ValueError(f'altered runtime file: {rel}')
    if observed != set(expected):
        raise ValueError(f'missing runtime entries: {sorted(set(expected) - observed)}')
    if stat.S_IMODE(root.stat().st_mode) != 0o755:
        raise ValueError('wrong runtime root mode')
    return {'format': 'arxo.mcp-verification-receipt/0.1', 'treeSha256': pin['treeSha256'], 'files': sum(row['type'] == 'file' for row in entries), 'result': 'pass', 'fullCorpus': 'not_checked', 'releaseVerified': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--pin', type=Path, required=True)
    parser.add_argument('--receipt', type=Path)
    args = parser.parse_args()
    try:
        if args.receipt and args.receipt.absolute().is_relative_to(args.root.absolute()):
            raise ValueError('receipt must be external')
        result = verify(args.root, args.pin)
        if args.receipt:
            args.receipt.write_bytes(canonical(result) + b'\n')
    except (ValueError, KeyError, TypeError, OSError) as error:
        parser.exit(1, f'verification refused: {error}\n')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
