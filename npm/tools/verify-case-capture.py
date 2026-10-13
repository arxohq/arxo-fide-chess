#!/usr/bin/env python3
"""Reproduce canonical fixtures through the pinned released CLI; never rewrite them."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tomllib


def sha(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--law', type=Path, required=True, help='Released law 0.2.3 binary')
parser.add_argument('--out', type=Path, required=True, help='New directory outside the repository')
args = parser.parse_args()
root = Path(__file__).resolve().parents[2]
out = args.out.resolve()
if out.exists() or out.is_relative_to(root):
    parser.error('Use a new output directory outside the repository')
law = args.law.resolve()
version = json.loads(subprocess.check_output([str(law), 'version', '--json']))
if version['tool'] != '0.2.3':
    parser.error('Fixture reproduction requires released CLI 0.2.3')
source = root / 'examples/arbiter'
cases = tomllib.loads((source / 'law.toml').read_text())['cases']
fixtures = json.loads((root / 'npm/examples/arbiter-cases.json').read_bytes())
provenance = json.loads((root / 'npm/examples/provenance.json').read_bytes())
records = {row['name']: row for row in provenance['cases']}
out.mkdir(parents=True)
checks = []
for case in cases:
    name = case['name']
    record = records[name]
    if sha((source / case['path']).read_bytes()) != record['sourceHash']:
        raise ValueError('Changed case source: ' + name)
    query = 'must-move.json' if name == 'TouchIntentUnknown' else 'loss.json'
    run = out / name
    with (out / (name + '.log')).open('w') as log:
        subprocess.run([str(law), 'ask', str(source), '--case', name,
                        '--query-json', str(source / 'queries' / query), '--out', str(run)],
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    raw = (run / 'request.json').read_bytes()
    request = json.loads(raw)
    if request['semanticVersion'] != '0.2.11':
        raise ValueError('Unexpected request semantics')
    value = request['case']
    captured = {'legalTime': value['context']['legalTime'],
                **{key: value[key] for key in ['assertions', 'context', 'constants', 'options'] if key in value}}
    if captured != fixtures[name] or sha(raw) != record['requestHash']:
        raise ValueError('Canonical capture differs: ' + name)
    checks.append({'case': name, 'sourceHash': record['sourceHash'], 'requestHash': sha(raw), 'passed': True})
report = {'format': 'arxo.fide-chess-case-reproduction/1', 'cli': version,
          'checks': checks, 'passed': True, 'releaseVerified': False, 'corpus': 'not_checked'}
(out / 'verification.json').write_text(json.dumps(report, indent=2) + '\n')
print('Reproduced all', len(checks), 'canonical case inputs and original request hashes')
