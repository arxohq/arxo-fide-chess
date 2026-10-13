#!/usr/bin/env python3
"""Offline source-surface guard; publisher selectors come from the pinned policy."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse
from .config import load as load_config, read_json, ref, relative


def digest(data):
    return 'sha256:' + hashlib.sha256(data).hexdigest()


def fragments(document, publisher_hosts):
    nodes = document.get('nodes', [])
    editions = {n.get('edition') for n in nodes if n.get('kind') == 'publication'
                and urlparse(n.get('uri', '')).hostname in publisher_hosts}
    result = []
    for node in nodes:
        if node.get('kind') != 'fragment' or node.get('edition') not in editions:
            continue
        for text in node.get('texts', []):
            value = text['text']
            result.append({'id': node['id'], 'edition': node['edition'],
                           'nodeContentHash': node['contentHash'],
                           'textSha256': digest(value.encode()),
                           'characters': len(value), 'bytes': len(value.encode()),
                           'status': text.get('status'), 'language': text.get('language')})
    return result


def check(root, runtime=None):
    root = Path(root).resolve()
    config = load_config(root)
    policy = read_json(ref(root, config, 'sourcePolicy'))
    canon = read_json(ref(root, config, 'canon'))
    legacy = config['legacyCnaf']
    if not legacy and policy.get('format') != 'arxo.mcp-source-policy/0.1':
        raise ValueError('Unsupported pinned source policy')
    publisher_hosts = ('caf.fr', 'www.caf.fr') if legacy else policy.get('publisherHosts', [])
    if not isinstance(publisher_hosts, (list, tuple)) or not publisher_hosts or any(not isinstance(host, str) or not host or '/' in host for host in publisher_hosts):
        raise ValueError('Source policy needs explicit publisher hosts')
    if policy['sourceCommit'] != canon['sourceCommit']:
        raise ValueError('source policy and frozen canon commits differ')
    distribution = policy['distribution']
    if distribution['fetchWithheld'] is not False or distribution['newReproductionRightsGranted'] is not False:
        raise ValueError('source policy must not fetch full withheld texts or grant new source rights')
    withheld_file = root / 'WITHHELD.json'
    withheld = read_json(withheld_file)['files'] if withheld_file.exists() else []
    actual_paths = sorted(f"packages/{x['package']}/{x['path']}" for x in withheld)
    if sorted(distribution['withheldPaths']) != actual_paths:
        raise ValueError('withheld paths differ from the publication manifest')
    for rel in actual_paths:
        relative(rel)
        path = root / rel
        if path.is_symlink() or path.exists():
            raise ValueError(f'withheld source present in public checkout: {rel}')
    expected = distribution['allowedExistingFragments']
    keys = [(x['package'], x['version'], x['id'], x['textSha256']) for x in expected]
    if len(keys) != len(set(keys)):
        raise ValueError('duplicate accepted excerpt')
    observed = []
    for publication in canon['publications']:
        if publication['role'] != 'root':
            continue
        name, version = publication['name'], publication['version']
        document = json.loads((root / f'registry/p/{name}/{version}/package.lawir.json').read_bytes())
        for item in fragments(document, publisher_hosts):
            observed.append({'package': name, 'version': version, **item})
        if runtime is not None:
            runtime_path = Path(runtime) / f"corpus/clir/{publication['runtimeKey']}.lawir.json"
            actual = json.loads(runtime_path.read_bytes())
            if fragments(actual, publisher_hosts) != fragments(document, publisher_hosts):
                raise ValueError(f'runtime source excerpts differ: {name}')
    order = lambda x: (x['package'], x['version'], x['id'], x['textSha256'])
    if sorted(observed, key=order) != sorted(expected, key=order):
        raise ValueError('Publisher excerpt IDs, hashes, text lengths or status differ from accepted public snapshot')
    if runtime is not None:
        runtime = Path(runtime)
        withheld_names = {Path(x['path']).name for x in withheld}
        for path in runtime.rglob('*'):
            rel = path.relative_to(runtime)
            if path.is_symlink():
                raise ValueError(f'runtime symlink is not allowed: {rel}')
            if {'analysis', 'drafts', 'tools', 'reviews', 'notes'}.intersection(rel.parts):
                raise ValueError(f'internal runtime path: {rel}')
            if path.is_file() and (path.name in withheld_names or path.suffix in ('.py', '.pyc', '.lawtest')
                                   or path.name in ('AUDIT.md', 'QUESTIONS.md', 'PLAN.ru.md')
                                   or path.name.startswith(('candidate-', 'phase-'))):
                raise ValueError(f'nonpublic runtime file: {rel}')
    return {'format': 'cnaf.mcp-source-check/1' if legacy else 'arxo.mcp-source-check/0.1', 'result': 'pass',
            'acceptedExistingExcerpts': len(observed), 'withheldFilesAbsent': len(actual_paths),
            'sourceCommit': policy['sourceCommit'], 'fullCorpus': 'not_checked', 'releaseVerified': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--runtime', type=Path)
    parser.add_argument('--receipt', type=Path)
    args = parser.parse_args()
    try:
        result = check(args.root, args.runtime)
        if args.receipt:
            args.receipt.write_text(json.dumps(result, sort_keys=True, indent=2) + '\n')
    except (KeyError, ValueError, OSError, TypeError) as error:
        parser.exit(1, f'source surface refused: {error}\n')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
