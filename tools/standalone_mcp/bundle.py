#!/usr/bin/env python3
"""Normalized runtime archive: ordered POSIX tar, epoch, UID/GID 0, gzip mtime 0."""
from __future__ import annotations
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import stat
import tarfile
from .verify import verify


def bundle(root, output, pin):
    root, output, pin = Path(root).absolute(), Path(output).absolute(), Path(pin).absolute()
    if output.is_relative_to(root) or output.exists() or output.is_symlink():
        raise ValueError('archive must be a new external file')
    result = verify(root, pin)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as raw:
        with gzip.GzipFile(fileobj=raw, filename='', mode='wb', mtime=0, compresslevel=9) as compressed:
            with tarfile.open(fileobj=compressed, mode='w', format=tarfile.PAX_FORMAT) as archive:
                paths = [root, *sorted(root.rglob('*'), key=lambda path: path.relative_to(root).as_posix())]
                for path in paths:
                    rel = 'runtime' if path == root else 'runtime/' + path.relative_to(root).as_posix()
                    info = tarfile.TarInfo(rel)
                    info.uid = info.gid = info.mtime = 0
                    info.uname = info.gname = ''
                    info.mode = stat.S_IMODE(path.stat().st_mode)
                    if path.is_dir():
                        info.type = tarfile.DIRTYPE
                        archive.addfile(info)
                    else:
                        info.size = path.stat().st_size
                        with path.open('rb') as stream:
                            archive.addfile(info, stream)
    archive_hash = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_name(output.name + '.sha256').write_text(f'{archive_hash}  {output.name}\n')
    return {'format': 'arxo.mcp-bundle-receipt/0.1', 'archiveSha256': 'sha256:' + archive_hash, 'treeSha256': result['treeSha256'], 'fullCorpus': 'not_checked', 'releaseVerified': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--pin', type=Path, required=True)
    parser.add_argument('--receipt', type=Path)
    args = parser.parse_args()
    try:
        if args.receipt and args.receipt.absolute().is_relative_to(args.root.absolute()):
            raise ValueError('receipt must be external')
        result = bundle(args.root, args.output, args.pin)
        if args.receipt:
            args.receipt.write_text(json.dumps(result, sort_keys=True, separators=(',', ':')) + '\n')
    except (ValueError, KeyError, OSError) as error:
        parser.exit(1, f'bundle refused: {error}\n')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
