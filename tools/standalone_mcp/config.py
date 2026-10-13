"""Small delivery configuration, independent of model/descriptor wire formats."""
from __future__ import annotations
import json
from pathlib import Path, PurePosixPath
import re

FORMAT = 'arxo.standalone-mcp-delivery/0.1'
DEFAULT_REFS = {
    'canon': 'mcp/canon.json', 'profile': 'mcp/profile.json',
    'sourcePolicy': 'mcp/source-policy.json', 'runtimePolicy': 'mcp/runtime-policy.json',
    'cases': 'mcp/cases/acceptance.json', 'runtimeLock': 'mcp/runtime.lock.json',
    'buildLock': 'mcp/build.lock.json', 'inputInventory': 'mcp/input-inventory.json',
    'runtimeContract': 'mcp/runtime-contract.json', 'hostCompatibility': 'mcp/host-compatibility.json',
    'treePin': 'mcp/tree.pin.json',
}


def relative(value):
    if not isinstance(value, str) or not value or '\\' in value or any(p in ('', '.', '..', '.git') for p in value.split('/')) or PurePosixPath(value).is_absolute():
        raise ValueError('Unsafe delivery relative path: ' + repr(value))
    return value


def read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate JSON field: ' + key)
            result[key] = value
        return result
    return json.loads(Path(path).read_bytes(), object_pairs_hook=unique, parse_constant=lambda v: (_ for _ in ()).throw(ValueError('Invalid JSON constant: ' + v)))


def load(root):
    root = Path(root).absolute()
    file = root / 'mcp/delivery.json'
    if not file.exists():
        canon_path = root / DEFAULT_REFS['canon']
        profile_path = root / DEFAULT_REFS['profile']
        if not canon_path.is_file() or not profile_path.is_file() or canon_path.is_symlink() or profile_path.is_symlink() or read_json(canon_path).get('format') != 'arxo.cnaf-canon/0.1' or read_json(profile_path).get('name') != 'cnaf':
            raise ValueError('Delivery configuration missing; only the explicit legacy CNAF contract is supported')
        # The legacy adapter keeps frozen CNAF artifacts and old entrypoints valid.
        return {'format': FORMAT, 'profileId': 'cnaf', 'producerRepository': 'arxohq/arxo-cnaf',
                'packageName': '@arxo/mcp-cnaf', 'refs': dict(DEFAULT_REFS), 'legacyCnaf': True}
    if file.is_symlink():
        raise ValueError('Delivery config must not be a symlink')
    config = read_json(file)
    allowed = {'format', 'profileId', 'producerRepository', 'packageName', 'refs', 'selectedPublications'}
    if config.get('format') != FORMAT or set(config) != allowed:
        raise ValueError('Unsupported/incomplete standalone delivery contract')
    profile = config['profileId']
    if not isinstance(profile, str) or not re.fullmatch(r'[a-z][a-z0-9]*(?:-[a-z0-9]+)*', profile):
        raise ValueError('Invalid standalone profile ID')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*', config['producerRepository']):
        raise ValueError('Invalid producer repository')
    if not re.fullmatch(r'@arxo/mcp-[a-z][a-z0-9-]*', config['packageName']):
        raise ValueError('Invalid MCP package name')
    if not isinstance(config['refs'], dict) or set(config['refs']) != set(DEFAULT_REFS):
        raise ValueError('Delivery refs must explicitly name every contract file')
    seen = set()
    for value in config['refs'].values():
        relative(value)
        if not value.startswith('mcp/') or value in seen:
            raise ValueError('Duplicate/out-of-surface delivery ref: ' + value)
        seen.add(value)
        current = root
        for part in value.split('/'):
            current /= part
            if current.is_symlink():
                raise ValueError('Delivery ref has a symlink: ' + value)
    entries = config['selectedPublications']
    if not isinstance(entries, list) or not entries:
        raise ValueError('Delivery needs selected publications')
    keys = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {'name', 'version', 'runtimeKey', 'packagePath', 'role'}:
            raise ValueError('Invalid selected publication fields')
        for field in ('name', 'version', 'runtimeKey'):
            if not isinstance(entry[field], str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', entry[field]):
                raise ValueError('Invalid selected publication identity')
        key = entry['name'], entry['version']
        if key in keys or entry['role'] not in ('root', 'dependency'):
            raise ValueError('Duplicate/invalid selected publication')
        keys.add(key)
        if not relative(entry['packagePath']).startswith('corpus/laws/'):
            raise ValueError('Package path is outside the runtime model surface')
    config['legacyCnaf'] = False
    return config


def ref(root, config, key):
    return Path(root) / config['refs'][key]


def env_prefix(config):
    return config['profileId'].replace('-', '_').upper() + '_MCP_'
