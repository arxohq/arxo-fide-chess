#!/usr/bin/env python3
"""Offline registry -> Rust MCP runtime. Python 3.12+, standard library only.

No model compilation, resolution service, network access or monorepo imports.
The destination must not exist. Pins and receipts are external to its tree.
"""
from __future__ import annotations
import argparse
import hashlib
from fractions import Fraction
import unicodedata
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tomllib
from .source_policy import check as check_source_policy
from .config import load as load_config, ref

VERSION = 'arxo.mcp-materializer/0.2'
HASH = re.compile(r'^sha256:[0-9a-f]{64}$')
TOKEN = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]*$')


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(data):
    return 'sha256:' + hashlib.sha256(data).hexdigest()


def fail(message):
    raise ValueError(message)


def relative(value):
    if not isinstance(value, str) or not value or '\\' in value:
        fail(f'invalid relative path: {value!r}')
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in ('', '.', '..') for part in value.split('/')):
        fail(f'path escape/noncanonical path: {value!r}')
    return path


def safe(root, value, *, missing=False):
    path = root.joinpath(*relative(value).parts)
    current = root
    for part in relative(value).parts:
        current = current / part
        if current.is_symlink():
            fail(f'symlink input forbidden: {current}')
    if not path.exists():
        if missing:
            return path
        fail(f'missing input: {path}')
    if not path.is_file():
        fail(f'input is not a regular file: {path}')
    return path


def read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                fail(f'{path}: duplicate JSON field {key}')
            result[key] = value
        return result
    return json.loads(path.read_bytes(), object_pairs_hook=unique, parse_constant=lambda x: fail(f'invalid JSON constant {x}'))


def checked_hash(data, expected, label):
    if not isinstance(expected, str) or not HASH.fullmatch(expected):
        fail(f'{label}: invalid sha256 pin {expected!r}')
    actual = digest(data)
    if actual != expected:
        fail(f'{label}: hash mismatch {actual} != {expected}')


def literal_normalize(value):
    """§208 typed value spellings, independently ported from the pinned format.

    Decimal is exact string arithmetic. No floating point or CLIR rewriting.
    """
    if isinstance(value, list):
        return [literal_normalize(item) for item in value]
    if not isinstance(value, dict):
        if isinstance(value, float) or isinstance(value, int) and not -(2**63) <= value < 2**63:
            fail('JSON number outside §208 signed integer range')
        if isinstance(value, str) and unicodedata.normalize('NFC', value) != value:
            fail('non-NFC string outside §208')
        return value
    result = {key: literal_normalize(item) for key, item in value.items()}
    if value.get('kind') != 'value':
        return result
    type_name = value.get('type', {}).get('name', '')
    kind = type_name.removeprefix('urn:law:std#') if type_name.startswith('urn:law:std#') else ''
    raw = value.get('value')
    if kind not in ('Decimal', 'Money', 'Quantity', 'Rational', 'Number') or not isinstance(raw, (str, int)) or isinstance(raw, bool):
        return result
    text = str(raw)
    if kind in ('Rational', 'Number'):
        if kind == 'Rational' and (not isinstance(raw, str) or not re.fullmatch(r'[+-]?[0-9]+/[+-]?[0-9]+', text)):
            return result
        if 'e' in text.lower() and len(text.lower().split('e')[-1].lstrip('+-0')) > 4:
            fail('number canonical expansion exceeds slice limit 4096')
        if 'e' in text.lower() and abs(int(text.lower().split('e')[-1])) > 4096:
            fail('number canonical expansion exceeds slice limit 4096')
        try:
            if '/' in text:
                numerator, denominator = text.split('/')
                fraction = Fraction(int(numerator), int(denominator))
            else:
                fraction = Fraction(text)
        except (ValueError, ZeroDivisionError):
            return result
        result['value'] = f'{fraction.numerator}/{fraction.denominator}'
        return result
    match = re.fullmatch(r'([+-]?)([0-9]*)(?:\.([0-9]*))?(?:[eE]([+-]?[0-9]+))?', text)
    if not match or not (match[2] or match[3]):
        return result
    digits = match[2] + (match[3] or '')
    if set(digits) <= {'0'}:
        result['value'] = '0'
        return result
    exponent = int(match[4] or '0')
    point = len(match[2]) + exponent
    if len(digits.rstrip('0')) - point > 4096 or point - len(digits) > 4096:
        fail('decimal canonical expansion exceeds slice limit 4096')
    if point <= 0:
        integer, fraction = '0', '0' * (-point) + digits
    elif point >= len(digits):
        integer, fraction = digits + '0' * (point - len(digits)), ''
    else:
        integer, fraction = digits[:point], digits[point:]
    integer = integer.lstrip('0') or '0'
    fraction = fraction.rstrip('0')
    result['value'] = ('-' if match[1] == '-' else '') + integer + ('.' + fraction if fraction else '')
    return result


def resource_hash(raw, resource):
    kind = resource['kind']
    if kind in ('label-overlay', 'parameter-dataset', 'decision-table'):
        value = json.loads(raw)
        if kind in ('parameter-dataset', 'decision-table'):
            value.pop('metadata', None)
            value.pop('labels', None)
            for key in ('values', 'rows'):
                for row in value.get(key, []):
                    row.pop('labels', None)
            if kind == 'decision-table' and value.get('hitPolicy') not in ('first', 'multiple'):
                value['rows'] = sorted(value.get('rows', []), key=lambda row: row.get('id', ''))
        return digest(canonical(literal_normalize(value)))
    return digest(raw)


def validate_runtime_lock(lock):
    if lock.get('format') != 'arxo.mcp-runtime-lock/0.1':
        fail('unsupported runtime lock format')
    host = lock.get('host', {})
    version = host.get('version', '')
    if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]+)?', version):
        fail('host version must be exact')
    if not host.get('platforms'):
        fail('host platforms must be pinned')
    for platform, entry in host['platforms'].items():
        if platform not in ('linux-amd64', 'darwin-arm64'):
            fail(f'unsupported runtime platform: {platform}')
        if not entry.get('url', '').startswith('https://') or 'latest' in entry['url'] or '/main/' in entry['url'] or '/master/' in entry['url']:
            fail(f'host artifact URL is not immutable: {platform}')
        for field in ('archiveSha256', 'binarySha256'):
            if not HASH.fullmatch(entry.get(field, '')):
                fail(f'host artifact needs exact {field}: {platform}')
        relative(entry['binaryPath'])
    targets = set()
    for asset in lock.get('assets', []):
        relative(asset['source']); target = str(relative(asset['target']))
        if not (any(target.startswith('packs/' + kind + '/') for kind in ('verb', 'rule', 'answer')) or target in ('notices/host.NOTICE', 'notices/LICENSE.host', 'spec/schema/legal-ir.schema.json')) or target in targets:
            fail(f'duplicate/undeclared runtime asset target: {target}')
        if not HASH.fullmatch(asset.get('sha256', '')):
            fail(f'asset needs exact raw sha256: {target}')
        targets.add(target)


def load_inputs(root):
    config = load_config(root)
    canon = read_json(safe(root, config['refs']['canon']))
    if not re.fullmatch(r'[0-9a-f]{40}', canon.get('sourceCommit', '')):
        fail('canon sourceCommit must be an exact commit')
    expected_format = 'arxo.cnaf-canon/0.1' if config['legacyCnaf'] else 'arxo.mcp-canon/0.1'
    if canon.get('format') != expected_format:
        fail('unsupported canon format')
    for token in (canon['id'], canon['version']):
        if not TOKEN.fullmatch(token):
            fail(f'invalid canon id/version: {token}')
    registry = {}
    for path in sorted((root / 'registry/p').glob('*/*.json')):
        if path.name == 'versions.json':
            continue
        desc = read_json(safe(root, path.relative_to(root).as_posix()))
        identity = desc['name'], desc['version']
        if not all(TOKEN.fullmatch(v) for v in identity):
            fail(f'invalid publication identity: {identity}')
        expected = f'registry/p/{identity[0]}/{identity[1]}.json'
        if path.relative_to(root).as_posix() != expected or identity in registry:
            fail(f'duplicate/mismatched descriptor identity: {path}')
        registry[identity] = desc
    entries = {}
    keys, namespaces, paths = set(), set(), set()
    for entry in canon['publications']:
        identity = entry['name'], entry['version']
        if identity in entries:
            fail(f'duplicate publication: {identity}')
        if identity not in registry:
            fail(f'missing registry publication: {identity}')
        desc = registry[identity]
        if entry['namespace'] != desc['namespace']:
            fail(f'namespace mismatch: {identity}')
        for field, value in entry['hashes'].items():
            actual = desc.get(field)
            if value != actual:
                fail(f'{identity}: pinned {field} mismatch')
        if entry['role'] not in ('root', 'dependency', 'excluded'):
            fail(f'{identity}: unknown role')
        if entry['role'] != 'excluded':
            key = entry['runtimeKey']
            if not TOKEN.fullmatch(key) or key in keys:
                fail(f'duplicate/invalid runtime key: {key}')
            if entry['namespace'] in namespaces:
                fail(f'duplicate namespace: {entry["namespace"]}')
            package_path = str(relative(entry['packagePath']))
            if not package_path.startswith('corpus/laws/') or package_path in paths:
                fail(f'duplicate/invalid packagePath: {package_path}')
            keys.add(key); namespaces.add(entry['namespace']); paths.add(package_path)
        entries[identity] = entry
    if not config['legacyCnaf']:
        declared = [{k: e[k] for k in ('name', 'version', 'runtimeKey', 'packagePath', 'role')} for e in entries.values() if e['role'] != 'excluded']
        if sorted(declared, key=lambda e: (e['name'], e['version'])) != sorted(config['selectedPublications'], key=lambda e: (e['name'], e['version'])):
            fail('delivery selected publications differ from pinned canon')
    if set(entries) != set(registry):
        fail('all registry publications must have explicit roles')
    selected = {identity: e for identity, e in entries.items() if e['role'] != 'excluded'}
    if len({name for name, version in selected}) != len(selected):
        fail('ambiguous versions for runtime package name')
    roots = {identity for identity, e in entries.items() if e['role'] == 'root'}
    if len(roots) != canon['expectedRootCount'] or not roots:
        fail('root count mismatch')
    clirs = {}
    closure = set()
    pending = list(roots)
    while pending:
        identity = pending.pop()
        if identity in closure:
            continue
        if identity not in selected:
            fail(f'import has no selected pinned publication: {identity}')
        closure.add(identity)
        desc = registry[identity]
        path = safe(root, f'registry/p/{identity[0]}/{identity[1]}/package.lawir.json')
        raw = path.read_bytes()
        checked_hash(raw, desc['contentHash'], str(path))
        clir = read_json(path)
        if any(clir['package'].get(field) != desc[field] for field in ('name', 'version', 'namespace')):
            fail(f'CLIR package identity mismatch: {identity}')
        imports = clir.get('imports', [])
        declared = {(d['name'], d['version']): d for d in desc.get('dependencies', [])}
        actual = {(i['package']['name'], i['package']['version']): i for i in imports}
        if len(actual) != len(imports) or set(actual) != set(declared):
            fail(f'descriptor imports differ from raw CLIR: {identity}')
        for target, imported in actual.items():
            if target not in registry:
                fail(f'missing import: {target}')
            target_desc = registry[target]
            for value in (declared[target], {**imported['package'], 'contentHash': imported['contentHash']}):
                if any(value.get(field) != target_desc.get(field) for field in ('name', 'version', 'namespace', 'contentHash')):
                    fail(f'import pin mismatch: {identity} -> {target}')
            pending.append(target)
        clirs[identity] = (path, clir)
    if closure != set(selected):
        fail('selected publications do not equal root import closure')
    return canon, registry, entries, clirs


def inventory(root):
    result = []
    for path in sorted(root.rglob('*'), key=lambda path: path.relative_to(root).as_posix()):
        mode = path.lstat().st_mode
        rel = path.relative_to(root).as_posix()
        if stat.S_ISLNK(mode) or not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
            fail(f'nonregular runtime entry: {rel}')
        expected = 0o755 if path.is_dir() or rel == 'bin/law-mcp-server' else 0o644
        if stat.S_IMODE(mode) != expected:
            fail(f'runtime mode mismatch: {rel}')
        row = {'path': rel, 'type': 'directory' if path.is_dir() else 'file', 'mode': f'{expected:04o}'}
        if path.is_file():
            raw = path.read_bytes()
            row.update(size=len(raw), sha256=digest(raw))
        result.append(row)
    return result


def materialize(root, output, *, host=None, platform='linux-amd64', receipt=None, tree_pin=None):
    root = Path(root).absolute()
    output = Path(output).absolute()
    if root.is_symlink() or output.is_symlink() or output.exists():
        fail('source/output symlink or existing output directory')
    if output.is_relative_to(root):
        fail('runtime output must be outside input checkout')
    for path in (receipt, tree_pin):
        if path and Path(path).absolute().is_relative_to(output):
            fail('receipt/tree pin must be outside runtime tree')
    config = load_config(root)
    canon, registry, entries, clirs = load_inputs(root)
    profile = read_json(safe(root, config['refs']['profile']))
    root_keys = sorted(e['runtimeKey'] for e in entries.values() if e['role'] == 'root')
    borrowed = sorted(e['runtimeKey'] for e in entries.values() if e['role'] == 'dependency')
    if profile.get('name') != config['profileId'] or profile.get('canon') != f'{canon["id"]}/{canon["version"]}':
        fail('MCP profile/canon binding mismatch')
    if profile.get('prefixes') != root_keys or profile.get('borrowed', []) != borrowed:
        fail('profile must select exact root keys and computed borrowed closure')
    if config['legacyCnaf'] and profile.get('calendarPackage') is not None:
        fail('CNAF preview calendarPackage must be null')
    lock = read_json(safe(root, config['refs']['runtimeLock']))
    validate_runtime_lock(lock)
    policy = read_json(safe(root, config['refs']['sourcePolicy']))
    source_check = check_source_policy(root)
    withheld = set(policy.get('distribution', {}).get('withheldPaths', []))
    for path in withheld:
        relative(path)
    frozen_path = safe(root, config['refs']['inputInventory'])
    frozen = read_json(frozen_path)
    inventory_format = 'cnaf.mcp-input-inventory/1' if config['legacyCnaf'] else 'arxo.mcp-input-inventory/0.1'
    if frozen.get('format') != inventory_format or frozen.get('sourceCommit') != canon['sourceCommit']:
        fail('frozen input inventory/source commit mismatch')
    frozen_files = {}
    for record in frozen['files']:
        rel = str(relative(record['path']))
        if rel in frozen_files:
            fail(f'duplicate frozen input path: {rel}')
        frozen_files[rel] = record
    if not config['legacyCnaf']:
        for rel, record in frozen_files.items():
            raw = safe(root, rel).read_bytes()
            if len(raw) != record['bytes'] or digest(raw) != 'sha256:' + record['sha256']:
                fail(f'frozen model/scenario/source input differs: {rel}')
    def frozen_check(source):
        if source.is_relative_to(root):
            rel = source.relative_to(root).as_posix()
            if rel.startswith('mcp/'):
                return
            if rel not in frozen_files:
                fail(f'input outside frozen inventory: {rel}')
            raw = source.read_bytes(); record = frozen_files[rel]
            if len(raw) != record['bytes'] or digest(raw) != 'sha256:' + record['sha256']:
                fail(f'frozen input raw bytes mismatch: {rel}')
    for identity in clirs:
        frozen_check(safe(root, f'registry/p/{identity[0]}/{identity[1]}.json'))
    copies = {}
    provenance = []
    def add(source, target, mode=0o644):
        source = safe(root, source) if isinstance(source, str) else source
        frozen_check(source)
        target = str(relative(target))
        if target in copies:
            if copies[target][0].read_bytes() != source.read_bytes():
                fail(f'conflicting runtime target: {target}')
            return
        copies[target] = (source, mode, digest(source.read_bytes()))
    packages = []
    resources = []
    for identity in sorted(clirs):
        entry = entries[identity]; desc = registry[identity]
        src, clir = clirs[identity]
        add(src, f'corpus/clir/{entry["runtimeKey"]}.lawir.json')
        if not config['legacyCnaf']:
            add(f'registry/p/{identity[0]}/{identity[1]}.json', f'metadata/descriptors/{entry["runtimeKey"]}.json')
            for hash_field, target_dir in [('questionCatalogHash', 'question-catalogs'), ('editorSourceMapHash', 'source-maps'), ('taskGuideCatalogHash', 'task-guides')]:
                metadata_hash = desc.get(hash_field)
                if metadata_hash:
                    if not HASH.fullmatch(metadata_hash):
                        fail(f'invalid descriptor metadata hash: {hash_field}')
                    metadata_source = safe(root, 'registry/r/sha256/' + metadata_hash.removeprefix('sha256:'))
                    checked_hash(metadata_source.read_bytes(), metadata_hash, str(metadata_source))
                    add(metadata_source, f'metadata/{target_dir}/{entry["runtimeKey"]}.json')
        base_rel = f'packages/{identity[0]}'
        package_root = root / base_rel
        manifest_path = safe(root, base_rel + '/law.toml')
        manifest = tomllib.loads(manifest_path.read_text())
        if any(manifest['package'].get(k) != desc[k] for k in ('name', 'version', 'namespace')):
            fail(f'package manifest identity mismatch: {identity}')
        lock_path = safe(root, base_rel + '/law.lock')
        package_lock = read_json(lock_path)
        if any(package_lock['root'].get(k) != desc[k] for k in ('name', 'version', 'namespace')):
            fail(f'lock root identity mismatch: {identity}')
        if package_lock.get('languageSemantics') != desc.get('languageSemantics'):
            fail(f'lock semantics mismatch: {identity}')
        for field, expected in [('artifactHash', desc['contentHash']), ('sourceHash', desc.get('sourceHash'))]:
            if package_lock['root'].get(field) != expected:
                fail(f'lock root {field} mismatch: {identity}')
        for dependency in package_lock.get('packages', []):
            dep_id = dependency['name'], dependency['version']
            if dep_id not in clirs:
                fail(f'lock dependency outside closure: {dep_id}')
            target = registry[dep_id]
            for field, expected in [('namespace', target['namespace']), ('artifactHash', target['contentHash']), ('sourceHash', target.get('sourceHash'))]:
                if dependency.get(field) != expected:
                    fail(f'lock dependency {field} mismatch: {identity} -> {dep_id}')
        files = {'law.toml', 'law.lock'}
        for optional in ('package-info.json', 'LICENSE', 'NOTICE'):
            if safe(root, f'{base_rel}/{optional}', missing=True).exists():
                files.add(optional)
        for resource in package_lock.get('resources', []):
            path = safe(package_root, resource['path'])
            raw = path.read_bytes()
            actual = resource_hash(raw, resource)
            if actual != resource['contentHash']:
                fail(f'resource hash mismatch: {path}: {actual} != {resource["contentHash"]}')
            files.add(str(relative(resource['path'])))
            resources.append({'package': identity[0], 'path': resource['path'], 'kind': resource['kind'], 'contentHash': resource['contentHash'], 'rawSha256': digest(raw)})
        for path in sorted(package_root.glob('i18n/*.json')):
            files.add(path.relative_to(package_root).as_posix())
        for rel in clir.get('metadata', {}).get('localSources', {}).values():
            full_rel = f'{base_rel}/{relative(rel)}'
            path = safe(root, full_rel, missing=True)
            if full_rel in withheld:
                if path.exists():
                    fail(f'withheld source unexpectedly present: {full_rel}')
            else:
                if not path.exists():
                    fail(f'missing local source: {full_rel}')
                files.add(rel)
        # Local dependency blobs remain inputs; do not discard deps as a cache.
        for path in sorted(package_root.glob('deps/*.lawir.json')):
            raw = safe(root, path.relative_to(root).as_posix()).read_bytes()
            value = read_json(path)
            dep_id = value['package']['name'], value['package']['version']
            if dep_id not in clirs:
                fail(f'unpinned deps blob: {path}')
            checked_hash(raw, registry[dep_id]['contentHash'], str(path))
            files.add(path.relative_to(package_root).as_posix())
        for rel in sorted(files):
            add(f'{base_rel}/{rel}', f'{entry["packagePath"]}/{rel}')
        packages.append({k: desc[k] for k in ('name', 'version', 'namespace', 'contentHash', 'features')})
        provenance.append({'name': identity[0], 'version': identity[1], 'runtimeKey': entry['runtimeKey'], 'hashes': {'descriptor': {k: desc.get(k) for k in ('sourceHash', 'contentHash', 'artifactHash', 'semanticHash', 'languageSemantics')}, 'clir': {k: clir.get(k) for k in ('artifactHash', 'semanticHash', 'theoryHash', 'schemaVersion', 'semanticVersion')}, 'lock': {'sourceHash': package_lock['root'].get('sourceHash'), 'artifactHash': package_lock['root'].get('artifactHash'), 'languageSemantics': package_lock.get('languageSemantics')}, 'rawSha256': digest(src.read_bytes())}})
    for asset in lock.get('assets', []):
        path = safe(root, asset['source'])
        pin = asset['sha256']
        if not pin.startswith('sha256:'):
            pin = 'sha256:' + pin
        checked_hash(path.read_bytes(), pin, str(path))
        add(path, asset['target'])
    host_hash = None
    if host:
        host = Path(host).absolute()
        if host.is_symlink() or not host.is_file():
            fail('host must be a regular file')
        host_hash = lock['host']['platforms'][platform]['binarySha256']
        if not host_hash.startswith('sha256:'):
            host_hash = 'sha256:' + host_hash
        checked_hash(host.read_bytes(), host_hash, 'released host')
        add(host, 'bin/law-mcp-server', 0o755)
    for rel in ('LICENSE', 'NOTICE'):
        add(rel, rel)
    for key in ('sourcePolicy', 'runtimePolicy', 'runtimeLock'):
        add(config['refs'][key], 'mcp/' + {'sourcePolicy': 'source-policy.json', 'runtimePolicy': 'runtime-policy.json', 'runtimeLock': 'runtime.lock.json'}[key])
    canon_artifact = {'schemaVersion': 'law.profile/0.1', 'id': canon['id'], 'version': canon['version'], 'kind': canon.get('kind', 'jurisdiction'), 'title': canon.get('title', 'Modèles indépendants Arxo des prestations françaises' if config['legacyCnaf'] else canon['id']), 'asOf': canon.get('asOf', '2026-10-13'), 'language': '0.2', 'semanticsRevision': canon.get('semanticsRevision', '0.2.0'), 'packages': packages}
    canon_artifact['contentHash'] = digest(canonical(canon_artifact))
    output.mkdir(parents=True, mode=0o755)
    for target, (source, mode, raw_pin) in sorted(copies.items()):
        path = output / target
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, path)
        checked_hash(path.read_bytes(), raw_pin, f'copied input {target}')
        path.chmod(mode)
    for rel, value in [(f'apps/mcp/profiles/{config["profileId"]}.json', profile), (f'corpus/profiles/{canon["id"]}/{canon["version"]}/profile.json', canon_artifact)]:
        path = output / rel; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(canonical(value) + b'\n'); path.chmod(0o644)
    for path in output.rglob('*'):
        if path.is_dir():
            path.chmod(0o755)
    output.chmod(0o755)
    check_source_policy(root, output)
    files = inventory(output)
    tree_digest = digest(canonical(files))
    pin = {'format': 'arxo.mcp-tree-pin/0.1', 'algorithm': 'sha256-canonical-inventory-v1', 'treeSha256': tree_digest, 'entries': files}
    result = {'format': 'arxo.mcp-materialization-receipt/0.1', 'toolVersion': VERSION, 'canon': f'{canon["id"]}/{canon["version"]}', ('cnafCommit' if config['legacyCnaf'] else 'sourceCommit'): canon['sourceCommit'], 'treeSha256': tree_digest, 'hostSha256': host_hash, 'platform': platform if host else None, 'publications': provenance, 'resources': resources, 'checks': {'sourcePolicy': source_check}, 'inputInventorySha256': digest(frozen_path.read_bytes()), 'policyDigests': {config['refs'][key]: digest(safe(root, config['refs'][key]).read_bytes()) for key in ('sourcePolicy', 'runtimePolicy')}, 'fullCorpus': 'not_checked', 'releaseVerified': False}
    for path, value in ((tree_pin, pin), (receipt, result)):
        if path:
            path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(canonical(value) + b'\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--host', type=Path)
    parser.add_argument('--platform', default='linux-amd64')
    parser.add_argument('--receipt', type=Path)
    parser.add_argument('--tree-pin', type=Path)
    args = parser.parse_args()
    try:
        result = materialize(args.root, args.output, host=args.host, platform=args.platform, receipt=args.receipt, tree_pin=args.tree_pin)
    except (ValueError, KeyError, OSError, TypeError) as error:
        parser.exit(1, f'materialization refused: {error}\n')
    print(json.dumps({'treeSha256': result['treeSha256'], 'packages': len(result['publications']), 'fullCorpus': result['fullCorpus'], 'releaseVerified': result['releaseVerified']}, sort_keys=True))


if __name__ == '__main__':
    main()
