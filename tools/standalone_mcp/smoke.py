#!/usr/bin/env python3
"""Exercise the real pinned MCP binary or HTTPS endpoint, never an evaluator stub."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import queue
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request


PROTOCOL = '2025-03-26'
INIT = {'protocolVersion': PROTOCOL, 'capabilities': {}, 'clientInfo': {'name': 'arxo-standalone-mcp-acceptance', 'version': '1'}}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def clean_env(state, token='', origin=''):
    return {'PATH': '/usr/bin:/bin', 'HOME': str(state), 'LANG': 'C.UTF-8',
            'LAW_MCP_ARTIFACT_DIR': str(state / 'artifacts'), 'LAW_MCP_LOG': '0',
            'LAW_MCP_TOKEN': token, 'LAW_MCP_ALLOWED_ORIGINS': origin, 'LAW_MCP_CALL_TIMEOUT': '30'}


class Stdio:
    def __init__(self, host, root, state, timeout=45, profile="cnaf"):
        self.timeout = timeout
        self.proc = subprocess.Popen([str(host), '--root', str(root), '--profile', profile],
                                     env=clean_env(state), stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.lines = queue.Queue()
        self.errors = []
        def reader():
            for line in self.proc.stdout:
                self.lines.put(line)
            self.lines.put(None)
        def errors():
            for line in self.proc.stderr:
                self.errors.append(line)
        threading.Thread(target=reader, daemon=True).start()
        threading.Thread(target=errors, daemon=True).start()

    def call(self, request):
        self.proc.stdin.write(json.dumps(request, separators=(',', ':')) + '\n')
        self.proc.stdin.flush()
        try:
            line = self.lines.get(timeout=self.timeout)
        except queue.Empty:
            raise TimeoutError('MCP stdio did not answer within the acceptance timeout')
        if line is None:
            raise RuntimeError('MCP exited: ' + ''.join(self.errors[-10:]))
        result = json.loads(line)
        if result.get('id') != request['id']:
            raise ValueError('MCP response id mismatch')
        return result

    def notify(self, method):
        self.proc.stdin.write(json.dumps({'jsonrpc': '2.0', 'method': method}) + '\n')
        self.proc.stdin.flush()

    def close(self):
        self.proc.terminate()
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()


class Http:
    def __init__(self, url, token, origin='', timeout=45, health_url=None):
        self.url, self.token, self.origin, self.timeout = url.rstrip('/'), token, origin, timeout
        self.health_url = health_url
        self.timings = []

    def raw(self, request=None, token=None, origin=None, health=False):
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json', 'MCP-Protocol-Version': PROTOCOL}
        selected_token = self.token if token is None else token
        if selected_token:
            headers['Authorization'] = 'Bearer ' + selected_token
        selected_origin = self.origin if origin is None else origin
        if selected_origin:
            headers['Origin'] = selected_origin
        url = self.url
        if health:
            url = self.health_url or self.url.removesuffix('/mcp') + '/healthz'
        data = None if request is None else json.dumps(request).encode()
        req = urllib.request.Request(url, data=data, headers=headers, method='GET' if health else 'POST')
        started = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                raw = response.read()
                return response.status, json.loads(raw) if raw else None
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read())
        finally:
            self.timings.append({'operation': 'healthz' if health else request.get('method', ''), 'tool': request.get('params', {}).get('name') if request else None, 'elapsedMs': round((time.monotonic()-started)*1000, 3)})

    def call(self, request):
        code, result = self.raw(request)
        if code != 200:
            raise ValueError(f'HTTP MCP returned status {code}: {result}')
        if result.get('id') != request['id']:
            raise ValueError('MCP response id mismatch')
        return result

    def notify(self, method):
        code, result = self.raw({'jsonrpc': '2.0', 'method': method})
        if code != 202 or result is not None:
            raise AssertionError('Initialized notification did not receive HTTP 202 with an empty body')

    def close(self):
        pass


def payload(response):
    return response.get('result', {}).get('structuredContent', {})


def assert_case(case, response, host_sha=None):
    expected = case['expect']
    refused = 'error' in response or response.get('result', {}).get('isError') is True
    if expected.get('refusal'):
        if not refused:
            raise AssertionError('Required refusal returned a successful result')
        if 'errorCode' in expected and response.get('error', {}).get('code') != expected['errorCode']:
            raise AssertionError('Wrong refusal class: ' + json.dumps(response, ensure_ascii=False)[:400])
        if expected.get('structuredCode') and payload(response).get('code') != expected['structuredCode']:
            raise AssertionError('Unavailable service did not return its declared refusal code')
        if expected.get('refusalContains') and expected['refusalContains'] not in json.dumps(response, ensure_ascii=False):
            raise AssertionError('Refusal did not name its accepted reason')
        return
    if refused:
        raise AssertionError('Expected successful execution: ' + json.dumps(response, ensure_ascii=False)[:600])
    body = payload(response)
    if 'queryPackages' in expected:
        if body.get('kind')!='queryPage' or body.get('packages')!=expected['queryPackages'] or not body.get('rows') or body.get('materializations') != 0:
            raise AssertionError('Structural query did not preserve declared selected scope without inference')
        for field in ('snapshot','resultHash'):
            if not isinstance(body.get(field),str) or not body[field].startswith('sha256:'):
                raise AssertionError('Structural query does not bind its snapshot/result identity')
        return
    answer = body.get('answer', {})
    for field in ('truthStatus', 'evaluationStatus'):
        if field in expected and answer.get(field, body.get(field)) != expected[field]:
            raise AssertionError(f'{field}: expected {expected[field]}, got {answer.get(field, body.get(field))}')
    provenance = body.get('provenance', {})
    if provenance.get('legalTime') != case['legalTime']:
        raise AssertionError('Explicit legal date was not preserved in provenance')
    if host_sha and provenance.get('rustCodeHash', provenance.get('codeHash')) != 'sha256:' + host_sha:
        raise AssertionError('Execution provenance uses a different host binary')
    if expected.get('proof'):
        nodes = body.get('evaluation', {}).get('proofGraph', {}).get('nodes', [])
        if not any(n.get('kind') == 'rule_application' for n in nodes):
            raise AssertionError('Successful inferred result lacks a rule application proof')
    nodes = body.get('evaluation', {}).get('proofGraph', {}).get('nodes', [])
    required_rules = set(expected.get('requiredRules', []))
    actual_rules = {node.get('rule') for node in nodes if node.get('rule')}
    if not required_rules <= actual_rules:
        raise AssertionError('Required proof producers missing: ' + str(required_rules - actual_rules))
    if 'judgmentRequired' in expected:
        requests = body.get('judgmentRequests', [])
        if bool(requests) != bool(expected['judgmentRequired']):
            raise AssertionError('Judgment request presence differs from accepted expectation')
    if expected.get('noErrorIssues') and any(issue.get('severity') == 'error' for issue in body.get('issues', [])):
        raise AssertionError('Native evaluation returned an error issue')
    if expected.get('actualCitations'):
        fragments = [fragment for act in body.get('provenance', {}).get('acts', []) for fragment in act.get('fragments', [])]
        if not fragments:
            raise AssertionError('Required actual runtime citations missing')
    if 'runtimeCitationAnchors' in expected:
        actual_anchors = {fragment for act in body.get('provenance', {}).get('acts', []) for fragment in act.get('fragments', [])}
        missing = set(expected['runtimeCitationAnchors']) - actual_anchors
        if missing:
            raise AssertionError('Runtime citation anchors missing: ' + str(missing))
    context = case.get('request', {}).get('arguments', {}).get('context')
    if context and body.get('replayControl', {}).get('request', {}).get('context') != context:
        raise AssertionError('Replay provenance does not preserve caller instants/timezone')
    selected = case.get('request', {}).get('arguments', {}).get('selectedInterpretations')
    if selected and body.get('replayControl', {}).get('request', {}).get('selectedInterpretations') != selected:
        raise AssertionError('Replay provenance does not name the selected interpretation')
    if 'timezone' in expected and provenance.get('timezone') != expected['timezone']:
        raise AssertionError('Accepted timezone contract is not preserved')


def exercise(client, cases, host_sha, evidence, label, source_policy=None, catalog_keys=None, reference_requests=None):
    counter = 0
    def request(method, params=None):
        nonlocal counter
        counter += 1
        message = {'jsonrpc': '2.0', 'id': counter, 'method': method}
        if params is not None:
            message['params'] = params
        return client.call(message)
    init = request('initialize', INIT)
    if init.get('result', {}).get('protocolVersion') not in ('2025-03-26', '2025-06-18', '2024-11-05'):
        raise AssertionError('Initialize did not negotiate a supported MCP protocol')
    client.notify('notifications/initialized')
    evidence.append({'transport': label, 'id': 'initialize', 'response': init, 'status': 'passed'})
    listed = request('tools/list')
    names = {t['name'] for t in listed.get('result', {}).get('tools', [])}
    required = {'law_packages', 'law_ask', 'law_search', 'law_sources', 'law_rules'}
    if not required <= names:
        raise AssertionError('Reference/execution tools missing: ' + str(required - names))
    forbidden = {'law_check', 'law_argue', 'law_amend', 'law_loophole'}
    if forbidden & names:
        raise AssertionError('Unaccepted facets appear in discovery: ' + str(forbidden & names))
    evidence.append({'transport': label, 'id': 'tools-list', 'response': listed, 'status': 'passed'})
    probes = [{'name': 'law_packages', 'arguments': {'limit': 100}}, *(reference_requests or [])]
    for probe in probes:
        name, arguments = probe['name'], probe['arguments']
        response = request('tools/call', {'name': name, 'arguments': arguments})
        if 'error' in response or response.get('result', {}).get('isError') is True:
            raise AssertionError('Enabled reference operation failed: ' + name + ': ' + json.dumps(response)[:500])
        if name == 'law_packages':
            serialized = json.dumps(payload(response))
            if catalog_keys is not None:
                found = {p['package'] for p in payload(response).get('packages', [])}
                current = response
                seen_pages = set()
                while payload(current).get('next'):
                    follow = payload(current)['next']
                    key = json.dumps(follow, sort_keys=True)
                    if key in seen_pages or len(seen_pages) > 100:
                        raise AssertionError('Catalog pagination cycle')
                    seen_pages.add(key)
                    current = request('tools/call', {'name': follow.get('tool', follow.get('name')), 'arguments': follow['arguments']})
                    if 'error' in current or current.get('result', {}).get('isError') is True:
                        raise AssertionError('Catalog follow-up failed')
                    found.update(p['package'] for p in payload(current).get('packages', []))
                    evidence.append({'transport': label, 'id': 'catalog-page:'+str(len(seen_pages)), 'status': 'passed', 'response': current})
                if found != set(catalog_keys):
                    raise AssertionError('Catalog differs from exact accepted manifest: missing '+str(set(catalog_keys)-found)+'; extra '+str(found-set(catalog_keys)))
        evidence.append({'transport': label, 'id': name, 'status': 'passed', 'response': response})
    if source_policy:
        for fragment in source_policy['distribution']['allowedExistingFragments']:
            response = request('tools/call', {'name': 'law_sources', 'arguments': {
                'fragment': fragment['id'], 'language': fragment['language'],
                'status': fragment['status'], 'view': 'full', 'textLimit': 4096}})
            texts = []; end = 0; seen = set(); parts = []
            while True:
                rows = payload(response).get('fragments', [])
                if len(rows) != 1:
                    raise AssertionError('Pinned public source fragment missing/ambiguous: '+fragment['id'])
                row = rows[0]
                if row.get('fragment') != fragment['id'] or row.get('language') != fragment['language'] or row.get('status') != fragment['status'] or row.get('contentHash') != fragment['textSha256']:
                    raise AssertionError('Source page identity differs: '+fragment['id'])
                text = row['text']
                text_range = row.get('textRange')
                if text_range is not None:
                    if text_range.get('start') != end or text_range.get('end') != end + len(text) or text_range.get('total') != fragment['characters']:
                        raise AssertionError('Source page range overlaps/gaps or has the wrong total')
                elif row.get('next') or end or len(text) != fragment['characters']:
                    raise AssertionError('Paged source lacks its exact character range')
                end += len(text); texts.append(text); parts.append(response)
                follow = row.get('next')
                if not follow:
                    if end != fragment['characters']:
                        raise AssertionError('Source ended before the accepted full text')
                    break
                key = json.dumps(follow, sort_keys=True)
                if key in seen or len(seen) >= 100:
                    raise AssertionError('Source pagination cycle/unbounded continuation')
                seen.add(key)
                if follow.get('tool', follow.get('name')) != 'law_sources':
                    raise AssertionError('Source continuation changed the declared tool')
                response = request('tools/call', {'name': 'law_sources', 'arguments': follow['arguments']})
                if 'error' in response or response.get('result', {}).get('isError') is True:
                    raise AssertionError('Pinned source continuation failed')
            raw_text = ''.join(texts).encode()
            if len(raw_text) != fragment['bytes'] or hashlib.sha256(raw_text).hexdigest() != fragment['textSha256'].removeprefix('sha256:'):
                raise AssertionError('API source text differs from accepted pinned fragment: '+fragment['id'])
            evidence.append({'transport': label, 'id': 'source-policy:'+fragment['id'], 'status': 'passed', 'responses': parts})
    for case in cases:
        response = request('tools/call', case['request'])
        row = {'transport': label, 'id': case['id'], 'response': response}
        try:
            assert_case(case, response, host_sha)
            row['status'] = 'passed'
        except AssertionError as error:
            row.update(status='failed', error=str(error))
        evidence.append(row)


def run(args):
    document = json.loads(args.cases.read_text())
    profile = document.get('profileId', 'cnaf')
    if not isinstance(profile, str) or not profile or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in profile):
        raise ValueError('Invalid accepted profile ID')
    evidence = []
    measurements = []
    source_policy = json.loads(args.source_policy.read_text()) if args.source_policy else None
    host_sha = args.expected_host_sha256.removeprefix('sha256:') if args.expected_host_sha256 else sha(args.host) if args.host else None
    if args.expected_host_sha256 and args.host and host_sha != sha(args.host):
        raise ValueError('Supplied host differs from expected endpoint host pin')
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix=profile+'-mcp-smoke-') as scratch:
        state = Path(scratch)
        if args.transport in ('stdio', 'both'):
            client = Stdio(args.host.resolve(), args.root.resolve(), state, profile=profile)
            try:
                exercise(client, document['cases'], host_sha, evidence, 'stdio', source_policy, document['catalogExpectedKeys'], document.get('referenceRequests', []))
            finally:
                client.close()
        if args.transport in ('http', 'both'):
            proc = None
            token = args.token if args.url else args.token or 'acceptance-token-local-only'
            origin = args.origin if args.url else args.origin or 'https://' + profile + '-acceptance.invalid'
            url = args.url
            if not url:
                # Bind a disposable loopback port. External connectivity is separately disabled by Docker.
                import socket
                with socket.socket() as listener:
                    listener.bind(('127.0.0.1', 0))
                    port = listener.getsockname()[1]
                proc = subprocess.Popen([str(args.host.resolve()), '--root', str(args.root.resolve()), '--profile', profile, '--http', '--host', '127.0.0.1', '--port', str(port)], env=clean_env(state, token, origin), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                url = f'http://127.0.0.1:{port}/mcp'
            client = Http(url, token, origin, health_url=args.health_url)
            try:
                deadline = time.monotonic() + 30
                while True:
                    try:
                        code, body = client.raw(health=True)
                        if code == 200 and body.get('status') == 'ok' and body.get('profile') == profile:
                            break
                    except (OSError, urllib.error.URLError):
                        pass
                    if time.monotonic() > deadline:
                        raise TimeoutError('HTTP health did not become ready')
                    time.sleep(0.1)
                evidence.append({'transport': 'http', 'id': 'healthz', 'status': 'passed', 'response': body})
                init_request = {'jsonrpc': '2.0', 'id': 999, 'method': 'initialize', 'params': INIT}
                unauthenticated = client.raw(init_request, token='')[0]
                if args.auth_mode == 'bearer' and unauthenticated != 401:
                    raise AssertionError('Unauthenticated MCP request was not refused')
                if args.auth_mode == 'public' and unauthenticated != 200:
                    raise AssertionError('Declared public edge did not permit an unauthenticated initialize')
                if client.raw(init_request, origin='https://foreign-origin.invalid')[0] != 403:
                    raise AssertionError('Foreign Origin was not refused')
                evidence += [{'transport': 'http', 'id': 'auth-refusal' if args.auth_mode == 'bearer' else 'public-edge-initialize', 'status': 'passed'}, {'transport': 'http', 'id': 'origin-refusal', 'status': 'passed'}]
                exercise(client, document['cases'], host_sha, evidence, 'http-remote' if args.url else 'http', source_policy, document['catalogExpectedKeys'], document.get('referenceRequests', []))
                measurements.extend(client.timings)
            finally:
                if proc:
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()
    receipt = {'format': 'arxo.mcp-smoke-receipt/0.1', 'hostSha256': host_sha,
               'casesSha256': sha(args.cases), 'sourcePolicySha256': sha(args.source_policy) if args.source_policy else None, 'elapsedSeconds': round(time.monotonic()-started, 3),
               'profile': profile, 'endpointUrl': args.url, 'transport': 'http-remote' if args.url else args.transport, 'authMode': args.auth_mode,
               'measurements': measurements, 'networkIsolation': args.network_evidence, 'fullCorpus': 'not_checked', 'releaseVerified': False,
               'checks': evidence, 'status': 'failed' if any(x['status'] != 'passed' for x in evidence) else 'passed'}
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+'\n')
    failures = [x['id'] + ': ' + x.get('error', '') for x in evidence if x['status'] != 'passed']
    if failures:
        raise AssertionError('\n'.join(failures))
    print(json.dumps({'status': receipt['status'], 'checks': len(evidence), 'receipt': str(args.receipt)}))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', type=Path)
    ap.add_argument('--host', type=Path)
    ap.add_argument('--cases', type=Path, default=Path('mcp/cases/acceptance.json'))
    ap.add_argument('--receipt', type=Path, required=True)
    ap.add_argument('--source-policy', type=Path, help='Required public-source API acceptance policy')
    ap.add_argument('--transport', choices=('http', 'stdio', 'both'), default='both')
    ap.add_argument('--url')
    ap.add_argument('--health-url', help='Separate external health endpoint; defaults beside /mcp')
    ap.add_argument('--auth-mode', choices=('bearer', 'public'), default='bearer', help='Only public edge mode permits unauthenticated initialize')
    ap.add_argument('--expected-host-sha256', help='Exact released binary identity for endpoint proof checks')
    ap.add_argument('--token', default='')
    ap.add_argument('--origin', default='')
    ap.add_argument('--network-evidence', default='not_enforced', help='Recorded infrastructure evidence; this argument does not enforce isolation')
    args = ap.parse_args()
    if not args.url and (not args.root or not args.host):
        ap.error('Local smoke requires --root and --host')
    if args.url and args.transport != 'http':
        ap.error('Endpoint smoke requires --transport http')
    try:
        run(args)
    except Exception as error:
        if not args.receipt.exists():
            args.receipt.parent.mkdir(parents=True, exist_ok=True)
            args.receipt.write_text(json.dumps({'format': 'arxo.mcp-smoke-receipt/0.1', 'status': 'failed', 'fatalError': str(error), 'endpointUrl': args.url, 'transport': 'http-remote' if args.url else args.transport, 'fullCorpus': 'not_checked', 'releaseVerified': False}, ensure_ascii=False, indent=2)+'\n')
        raise


if __name__ == '__main__':
    main()
