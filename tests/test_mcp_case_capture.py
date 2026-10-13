#!/usr/bin/env python3
"""Verify captured MCP requests retain published fixtures; no subject evaluation."""
import copy
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
# Exact public fixture copies, without installing or exporting the model npm library.
FIXTURE_ALIASES = {'npm/examples/arbiter-cases.json': 'mcp/fixtures/arbiter-cases.json', 'npm/test/expectations.json': 'mcp/fixtures/expectations.json', 'npm/test/queries.json': 'mcp/fixtures/queries.json', 'npm/test/runtime.test.mjs': 'mcp/fixtures/runtime.test.mjs', 'npm/source-pin.json': 'mcp/fixtures/source-pin.json'}

def read(path):
    return json.loads((ROOT / FIXTURE_ALIASES.get(path,path)).read_text())

class CaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = read('mcp/cases/acceptance.json')
        cls.inputs = read('npm/examples/arbiter-cases.json')
        cls.queries = read('npm/test/queries.json')
        cls.expected = read('npm/test/expectations.json')
        cls.model = read('registry/p/fide.laws.chess/0.1.1/package.lawir.json')

    def test_source_fixture_hashes(self):
        for path, digest in self.cases['sourceFixtures']['files'].items():
            self.assertEqual('sha256:' + hashlib.sha256((ROOT / FIXTURE_ALIASES.get(path,path)).read_bytes()).hexdigest(), digest, path)
        self.assertEqual(len(self.inputs), 10)
        self.assertEqual(len(self.expected), 18)
        self.assertEqual(read('npm/source-pin.json')['revision'], self.cases['sourceFixtures']['sourceCommit'])

    def test_all_original_requests_and_expectations_preserved(self):
        retained = [item for item in self.cases['cases'] if 'fixture' in item]
        self.assertEqual(len(retained), 18)
        for item, expected in zip(retained, self.expected):
            fixture = self.inputs[expected['case']]
            request = item['request']['arguments']
            query = self.queries[Path(expected['query']).name]
            self.assertEqual(item['fixture']['case'], expected['case'])
            self.assertEqual(item['fixture']['query'], expected['query'])
            self.assertEqual(request['predicate'], query['literal']['predicate'])
            self.assertEqual(request['args'], query['literal']['args'])
            self.assertEqual(request['legalTime'], fixture['legalTime'])
            self.assertEqual(request['context'], {k:v for k,v in fixture['context'].items() if k != 'legalTime'})
            self.assertEqual(item['fixture']['assertionIds'], [a['id'] for a in fixture['assertions']])
            self.assertEqual(len(request['facts']), len(fixture['assertions']))
            for fact, assertion in zip(request['facts'], fixture['assertions']):
                self.assertEqual(fact['predicate'], assertion['literal']['predicate'])
                self.assertEqual(fact['args'], assertion['literal']['args'])
                self.assertEqual(fact['negated'] if 'negated' in fact else False, assertion['literal']['polarity'] == 'negative')
                self.assertEqual(fact['provenance']['origin'], assertion['origin'])
                self.assertEqual(assertion['evidence'], [])
            for field,value in expected.items():
                if field not in ('case','query'):
                    self.assertEqual(item['expect'][field], value)

    def test_absent_judgment_and_explicit_touch_are_distinct(self):
        unknown = self.cases['cases'][0]['request']['arguments']
        self.assertFalse(any(f['provenance']['origin'] == 'adjudicated' for f in unknown['facts']))
        explicit = next(c for c in self.cases['cases'] if c['id'] == 'touch-explicit-adjudicated')['request']['arguments']
        expected = copy.deepcopy(unknown)
        expected['facts'].append({'predicate':'urn:fide:laws:clir:chess#piece_touched_intentionally',
            'args':[{'kind':'entity_ref','id':'urn:example:chess:white'},{'kind':'entity_ref','id':'urn:example:chess:king'}],
            'provenance':{'origin':'adjudicated'}})
        self.assertEqual(explicit, expected)

    def test_static_source_join_is_from_exact_model(self):
        nodes = {n['id']:n for n in self.model['nodes']}
        for case in self.cases['cases']:
            for link in case['expect'].get('sourceAnchorLinks', []):
                self.assertEqual(nodes[link['rule']]['anchors'], link['anchors'])
                self.assertTrue(all(nodes[anchor]['kind'] == 'fragment' for anchor in link['anchors']))

    def test_source_policy_fragment_bytes(self):
        nodes = {n['id']:n for n in self.model['nodes']}
        policy = read('mcp/source-policy.json')
        self.assertFalse(policy['distribution']['fetchWithheld'])
        self.assertFalse(policy['distribution']['newReproductionRightsGranted'])
        fragments = policy['distribution']['allowedExistingFragments']
        self.assertEqual(len(fragments), 17)
        for row in fragments:
            node = nodes[row['id']]
            text = next(t['text'] for t in node['texts'] if t['language'] == row['language'] and t['status'] == row['status'])
            self.assertEqual(row['nodeContentHash'], node['contentHash'])
            self.assertEqual(row['textSha256'], 'sha256:' + hashlib.sha256(text.encode()).hexdigest())
            self.assertEqual(row['bytes'], len(text.encode()))

if __name__ == '__main__':
    unittest.main()
