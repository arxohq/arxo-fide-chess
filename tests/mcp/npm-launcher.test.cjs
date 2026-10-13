'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync, spawn } = require('node:child_process');
const { sha, canonical, verifySlice } = require('../../mcp/npm/bin/arxo-mcp.cjs');
const template = fs.readFileSync(path.resolve(__dirname, '../../mcp/npm/bin/arxo-mcp.cjs'), 'utf8');

function fixture(t, script = '#!/bin/sh\nprintf "args:%s\\nroot:%s\\naux:%s\\nstate:%s\\n" "$*" "$LAW_MCP_ROOT" "$LAW_NEURAL_URL" "$HOME"\n') {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'fide-launcher-test-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  fs.mkdirSync(path.join(root, 'slice'));
  fs.writeFileSync(path.join(root, 'slice/input.json'), '{}');
  const entries = [{ path: 'input.json', type: 'file', mode: '0644', size: 2, sha256: sha(Buffer.from('{}')) }];
  const key = process.platform + '-' + process.arch;
  const hostDir = path.join(root, 'node_modules/@arxo/mcp-host-' + key);
  fs.mkdirSync(path.join(hostDir, 'bin'), { recursive: true });
  fs.writeFileSync(path.join(hostDir, 'package.json'), JSON.stringify({ name: '@arxo/mcp-host-' + key, version: '0.4.2-cnafpreview.1' }));
  fs.writeFileSync(path.join(hostDir, 'bin/law-mcp-server'), script, { mode: 0o755 });
  const pin = { format: 'arxo.mcp-npm-pin/0.1', profile: 'fide-chess', data: { entries, treeSha256: sha(Buffer.from(canonical(entries))) },
    binaries: { [key]: { package: '@arxo/mcp-host-' + key, version: '0.4.2-cnafpreview.1', sha256: sha(Buffer.from(script)) } } };
  fs.writeFileSync(path.join(root, 'pin.json'), canonical(pin) + '\n');
  fs.writeFileSync(path.join(root, 'package.json'), '{"version":"0.1.0"}');
  fs.mkdirSync(path.join(root, 'bin'));
  const launcher = path.join(root, 'bin/arxo-mcp.cjs');
  fs.writeFileSync(launcher, template.replace('__PIN_SHA256__', sha(fs.readFileSync(path.join(root, 'pin.json')))));
  return { root, launcher, hostDir, pin };
}

test('fixed FIDE args, environment allowlist and temporary state cleanup', t => {
  const f = fixture(t);
  const r = spawnSync(process.execPath, [f.launcher], { encoding: 'utf8', env: { ...process.env, LAW_MCP_ROOT: '/wrong', LAW_NEURAL_URL: 'poison' } });
  assert.equal(r.status, 0, r.stderr);
  assert.match(r.stdout, /--profile fide-chess/);
  assert.equal(r.stdout.split('\n')[0], 'args:--root ' + fs.realpathSync(f.root) + '/slice --profile fide-chess');
  assert.match(r.stdout, /root:\naux:\n/);
  const state = r.stdout.match(/state:(.*)\n/)[1];
  assert.equal(fs.existsSync(state), false);
});
for (const [label, change, message] of [
  ['altered data', f => fs.writeFileSync(path.join(f.root, 'slice/input.json'), '[]'), /altered data/],
  ['missing data', f => fs.unlinkSync(path.join(f.root, 'slice/input.json')), /missing pinned/],
  ['extra file', f => fs.writeFileSync(path.join(f.root, 'slice/internal.txt'), 'private'), /unexpected data/],
  ['data symlink', f => { fs.unlinkSync(path.join(f.root, 'slice/input.json')); fs.symlinkSync('/etc/hosts', path.join(f.root, 'slice/input.json')); }, /unexpected data/],
  ['changed pin', f => fs.appendFileSync(path.join(f.root, 'pin.json'), ' '), /pin.json differs/],
  ['wrong binary', f => fs.appendFileSync(path.join(f.hostDir, 'bin/law-mcp-server'), '#wrong'), /host version\/binary differs/],
  ['wrong host version', f => fs.writeFileSync(path.join(f.hostDir, 'package.json'), '{"name":"wrong","version":"0"}'), /host version\/binary differs/],
  ['missing optional host', f => fs.rmSync(f.hostDir, { recursive: true }), /missing .*reinstall without/],
]) {
  test('refuses ' + label + ' before host execution', t => {
    const f = fixture(t); change(f);
    const r = spawnSync(process.execPath, [f.launcher], { encoding: 'utf8' });
    assert.equal(r.status, 2); assert.equal(r.stdout, ''); assert.match(r.stderr, message);
  });
}
test('host override args and invalid timeout are refused', t => {
  const f = fixture(t);
  for (const args of [['--root', '/wrong'], ['--http'], ['--profile', 'other']]) {
    const r = spawnSync(process.execPath, [f.launcher, ...args], { encoding: 'utf8' });
    assert.equal(r.status, 2); assert.equal(r.stdout, '');
  }
  for (const value of ['0', '111', '0.001', 'bogus']) {
    const r = spawnSync(process.execPath, [f.launcher], { encoding: 'utf8', env: { ...process.env, FIDE_CHESS_MCP_CALL_TIMEOUT: value } });
    assert.equal(r.status, 2); assert.match(r.stderr, /integer from 1 to 110/);
  }
});
test('unsafe pinned paths are refused', t => {
  const f = fixture(t);
  for (const name of ['../escape', '/absolute', 'a\\b', 'a//b', 'a/./b']) {
    const entries = [{ path: name, type: 'directory', mode: '0755' }];
    assert.throws(() => verifySlice(path.join(f.root, 'slice'), { data: { entries, treeSha256: sha(Buffer.from(canonical(entries))) } }), /unsafe pinned/);
  }
});
test('SIGTERM is forwarded and temporary state is removed', async t => {
  const f = fixture(t, '#!/bin/sh\nprintf "state:%s\\n" "$HOME"\nexec /bin/sleep 30\n');
  const p = spawn(process.execPath, [f.launcher], { stdio: ['ignore', 'pipe', 'pipe'] });
  const output = await new Promise((resolve, reject) => {
    p.stdout.once('data', b => resolve(b.toString())); p.once('error', reject);
  });
  const state = output.trim().slice(6);
  assert.equal(fs.existsSync(state), true);
  p.kill('SIGTERM');
  const code = await new Promise(resolve => p.once('exit', resolve));
  assert.equal(code, 143); assert.equal(fs.existsSync(state), false);
});
