"""Tiny independent registry fixtures: real negative boundaries, no host needed."""
from __future__ import annotations
import json
from pathlib import Path
import sys
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parents[2] / 'tools'
sys.path.insert(0, str(TOOLS))
from standalone_mcp import materialize as m


def write(root, rel, value):
    p = root / rel; p.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, bytes):
        p.write_bytes(value)
    else:
        p.write_bytes(m.canonical(value))
    return p


def fixture(root):
    rows = []
    for name in ('fr.dep', 'fr.root'):
        namespace = 'urn:test:' + name
        deps = []
        if name == 'fr.root':
            d = json.loads((root / 'registry/p/fr.dep/1.0.0.json').read_bytes())
            deps = [{k: d[k] for k in ('name', 'version', 'namespace', 'contentHash')}]
        head = {'name': name, 'version': '1.0.0', 'namespace': namespace}
        clir = {'schemaVersion': '0.2.0', 'package': head, 'nodes': [], 'imports': [{'package': {k: d[k] for k in ('name', 'version', 'namespace')}, 'contentHash': d['contentHash']} for d in deps]}
        raw = m.canonical(clir)
        desc = {**head, 'contentHash': m.digest(raw), 'languageSemantics': 'law.core/0.2.11', 'features': [], 'dependencies': deps}
        write(root, f'registry/p/{name}/1.0.0/package.lawir.json', raw)
        write(root, f'registry/p/{name}/1.0.0.json', desc)
        write(root, f'packages/{name}/law.toml', f'[package]\nname="{name}"\nversion="1.0.0"\nnamespace="{namespace}"\n'.encode())
        write(root, f'packages/{name}/law.lock', {'root': {**head, 'artifactHash': desc['contentHash']}, 'languageSemantics': desc['languageSemantics'], 'packages': [], 'resources': []})
        rows.append({**head, 'runtimeKey': name, 'packagePath': 'corpus/laws/' + name, 'role': 'root' if name == 'fr.root' else 'dependency', 'hashes': {'contentHash': desc['contentHash'], 'sourceHash': None}})
    write(root, 'mcp/canon.json', {'format': 'arxo.cnaf-canon/0.1', 'id': 'fr.benefits', 'version': '0.1.0', 'sourceCommit': 'a'*40, 'expectedRootCount': 1, 'publications': rows})
    write(root, 'mcp/profile.json', {'name': 'cnaf', 'canon': 'fr.benefits/0.1.0', 'prefixes': ['fr.root'], 'borrowed': ['fr.dep'], 'calendarPackage': None})
    write(root, 'mcp/runtime.lock.json', {'format': 'arxo.mcp-runtime-lock/0.1', 'host': {'version': '0.4.2', 'platforms': {'linux-amd64': {'url': 'https://example.org/0.4.2.tgz', 'archiveSha256': 'sha256:'+'1'*64, 'binarySha256': m.digest(b'host'), 'binaryPath': 'package/bin/law-mcp-server'}}}, 'assets': []})
    write(root, 'mcp/source-policy.json', {'sourceCommit': 'a'*40, 'distribution': {'withheldPaths': [], 'fetchWithheld': False, 'newReproductionRightsGranted': False, 'allowedExistingFragments': []}})
    write(root, 'WITHHELD.json', {'files': []})
    write(root, 'mcp/runtime-policy.json', {})
    write(root, 'NOTICE', b'notice\n'); write(root, 'LICENSE', b'license\n')
    files = [{'path': path.relative_to(root).as_posix(), 'sha256': m.digest(path.read_bytes())[7:], 'bytes': path.stat().st_size} for path in sorted(root.rglob('*')) if path.is_file() and not path.relative_to(root).as_posix().startswith('mcp/')]
    write(root, 'mcp/input-inventory.json', {'format': 'cnaf.mcp-input-inventory/1', 'sourceCommit': 'a'*40, 'files': files})
    return root


class MaterializeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = fixture(self.base / 'source')
        self.output = self.base / 'runtime'

    def tearDown(self):
        self.temp.cleanup()

    def edit(self, path, fn):
        value = json.loads((self.root / path).read_bytes()); fn(value); write(self.root, path, value)

    def refuses(self, text):
        with self.assertRaisesRegex(ValueError, text):
            m.materialize(self.root, self.output)
        self.assertFalse(self.output.exists(), 'invalid inputs must fail before output creation')

    def test_exact_closure_raw_bytes_and_missing_hash(self):
        result = m.materialize(self.root, self.output, tree_pin=self.base / 'pin.json')
        self.assertEqual(len(result['publications']), 2)
        for name in ('fr.root', 'fr.dep'):
            self.assertEqual((self.output / f'corpus/clir/{name}.lawir.json').read_bytes(), (self.root / f'registry/p/{name}/1.0.0/package.lawir.json').read_bytes())
        self.assertIsNone(result['publications'][0]['hashes']['descriptor']['sourceHash'])
        self.assertFalse(result['releaseVerified'])

    def test_raw_clir_hash_mismatch(self):
        with (self.root / 'registry/p/fr.root/1.0.0/package.lawir.json').open('ab') as f:
            f.write(b' ')
        self.refuses('hash mismatch')

    def test_duplicate_runtime_key(self):
        self.edit('mcp/canon.json', lambda x: x['publications'][0].update(runtimeKey='fr.root'))
        self.refuses('duplicate/invalid runtime key')

    def test_duplicate_namespace(self):
        self.edit('registry/p/fr.root/1.0.0.json', lambda x: x.update(namespace='urn:test:fr.dep'))
        self.edit('mcp/canon.json', lambda x: x['publications'][1].update(namespace='urn:test:fr.dep'))
        self.refuses('duplicate namespace')

    def test_unclassified_publication(self):
        write(self.root, 'registry/p/extra/1.0.0.json', {'name': 'extra', 'version': '1.0.0'})
        self.refuses('all registry publications')

    def test_ambiguous_version(self):
        desc = json.loads((self.root / 'registry/p/fr.dep/1.0.0.json').read_bytes()); desc['version'] = '2.0.0'
        write(self.root, 'registry/p/fr.dep/2.0.0.json', desc)
        self.edit('mcp/canon.json', lambda x: x['publications'].append({**x['publications'][0], 'version': '2.0.0', 'runtimeKey': 'dep2', 'namespace': 'urn:test:dep2', 'packagePath': 'corpus/laws/dep2'}))
        self.edit('registry/p/fr.dep/2.0.0.json', lambda x: x.update(namespace='urn:test:dep2'))
        self.refuses('ambiguous versions')

    def test_missing_import(self):
        (self.root / 'registry/p/fr.dep/1.0.0.json').unlink()
        self.refuses('missing registry publication')

    def test_excluded_import(self):
        self.edit('mcp/canon.json', lambda x: x['publications'][0].update(role='excluded'))
        self.refuses('no selected pinned publication')

    def test_missing_resource(self):
        self.edit('packages/fr.root/law.lock', lambda x: x['resources'].append({'kind': 'document', 'path': 'missing.txt', 'contentHash': 'sha256:'+'0'*64}))
        self.refuses('missing input')

    def test_resource_mismatch(self):
        write(self.root, 'packages/fr.root/r.txt', b'resource')
        self.edit('packages/fr.root/law.lock', lambda x: x['resources'].append({'kind': 'document', 'path': 'r.txt', 'contentHash': 'sha256:'+'0'*64}))
        self.refuses('resource hash mismatch')

    def test_resource_path_escape(self):
        self.edit('packages/fr.root/law.lock', lambda x: x['resources'].append({'kind': 'document', 'path': '../secret', 'contentHash': 'sha256:'+'0'*64}))
        self.refuses('path escape')

    def test_symlink_escape(self):
        write(self.root, 'secret', b'x')
        (self.root / 'packages/fr.root/r.txt').symlink_to('../../secret')
        self.edit('packages/fr.root/law.lock', lambda x: x['resources'].append({'kind': 'document', 'path': 'r.txt', 'contentHash': m.digest(b'x')}))
        self.refuses('symlink input')

    def test_profile_broad_selector(self):
        self.edit('mcp/profile.json', lambda x: x.update(prefixes=['fr-']))
        self.refuses('exact root keys')

    def test_receipt_inside_output(self):
        with self.assertRaisesRegex(ValueError, 'outside runtime'):
            m.materialize(self.root, self.output, receipt=self.output / 'receipt.json')

    def test_existing_output(self):
        self.output.mkdir()
        with self.assertRaisesRegex(ValueError, 'existing output'):
            m.materialize(self.root, self.output)

    def test_lock_root_pin_mismatch(self):
        self.edit('packages/fr.root/law.lock', lambda x: x['root'].update(artifactHash='sha256:'+'0'*64))
        self.refuses('lock root artifactHash mismatch')

    def test_host_latest_refused(self):
        self.edit('mcp/runtime.lock.json', lambda x: x['host'].update(version='latest'))
        self.refuses('host version must be exact')

    def test_asset_path_escape(self):
        self.edit('mcp/runtime.lock.json', lambda x: x['assets'].append({'source': '../secret', 'target': 'packs/verb/a', 'sha256': 'sha256:'+'0'*64}))
        self.refuses('path escape')

    def test_decimal_canonical_form(self):
        for raw, expected in [('0.50', '0.5'), ('1.25e3', '1250'), ('-0.000', '0'), ('+0012.500', '12.5')]:
            value = {'kind': 'value', 'type': {'name': 'urn:law:std#Decimal'}, 'value': raw}
            self.assertEqual(m.literal_normalize(value)['value'], expected)

    def test_host_pinned_and_executable(self):
        host = self.base / 'host'; host.write_bytes(b'host')
        result = m.materialize(self.root, self.output, host=host)
        self.assertEqual(result['hostSha256'], m.digest(b'host'))
        self.assertEqual((self.output / 'bin/law-mcp-server').stat().st_mode & 0o777, 0o755)

    def test_frozen_source_mutation(self):
        (self.root / 'LICENSE').write_text('changed')
        self.refuses('frozen input raw bytes mismatch')

    def test_frozen_source_missing(self):
        self.edit('mcp/input-inventory.json', lambda x: x.update(files=[r for r in x['files'] if r['path'] != 'NOTICE']))
        self.refuses('outside frozen inventory')

    def test_source_commit_mismatch(self):
        self.edit('mcp/input-inventory.json', lambda x: x.update(sourceCommit='b'*40))
        self.refuses('frozen input inventory/source commit mismatch')

    def test_source_policy_fetch_refused(self):
        self.edit('mcp/source-policy.json', lambda x: x['distribution'].update(fetchWithheld=True))
        self.refuses('must not fetch')

    def test_source_policy_changed_excerpt_refused(self):
        self.edit('mcp/source-policy.json', lambda x: x['distribution']['allowedExistingFragments'].append({'package': 'fr.root', 'version': '1.0.0', 'id': 'extra', 'textSha256': 'sha256:'+'0'*64}))
        self.refuses('excerpt IDs')

    def test_decimal_custom_type_is_not_reinterpreted(self):
        value = {'kind': 'value', 'type': {'name': 'urn:test:custom#Decimal'}, 'value': '01.00'}
        self.assertEqual(m.literal_normalize(value), value)

    def schema_asset(self, raw=b'{"$defs":{"node":{"type":"object"}}}'):
        source = 'mcp/assets/spec/schema/legal-ir.schema.json'
        write(self.root, source, raw)
        self.edit('mcp/runtime.lock.json', lambda x: x['assets'].append({'source': source, 'target': 'spec/schema/legal-ir.schema.json', 'sha256': m.digest(raw)}))
        return self.root / source

    def test_pinned_schema_asset_copied_raw(self):
        source = self.schema_asset()
        m.materialize(self.root, self.output)
        self.assertEqual((self.output / 'spec/schema/legal-ir.schema.json').read_bytes(), source.read_bytes())

    def test_missing_schema_asset_refused(self):
        self.schema_asset().unlink()
        self.refuses('missing input')

    def test_unpinned_schema_asset_refused(self):
        self.schema_asset()
        self.edit('mcp/runtime.lock.json', lambda x: x['assets'][0].pop('sha256'))
        self.refuses('exact raw sha256')

    def test_tampered_schema_asset_refused(self):
        self.schema_asset().write_bytes(b'{"changed":true}')
        self.refuses('hash mismatch')

    def test_a3_semantic_resource_hash(self):
        value = {'kind': 'parameter-dataset', 'metadata': {'private': 1}, 'labels': ['a'], 'values': [{'id': 'x', 'labels': ['b'], 'value': 4}]}
        expected = m.digest(m.canonical({'kind': 'parameter-dataset', 'values': [{'id': 'x', 'value': 4}]}))
        self.assertEqual(m.resource_hash(m.canonical(value), {'kind': 'parameter-dataset'}), expected)


if __name__ == '__main__':
    unittest.main()
