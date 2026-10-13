'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync, spawn } = require('node:child_process');
const { sha, canonical, verifySlice, parseProcStat, isNpmAncestor, captureLinuxAncestors, linuxAncestorsAlive, watchLinuxAncestors } = require('../../mcp/npm/bin/arxo-mcp.cjs');
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

function procStat(pid, parent, startTime = '42', state = 'S', command = 'node') {
  return Buffer.from(pid + ' (' + command + ') ' + [state, parent, ...Array(17).fill('0'), startTime].join(' ') + '\n');
}
function procFixture() {
  const files = new Map([
    ['/proc/100/stat', procStat(100, 50)],
    ['/proc/50/stat', procStat(50, 40, '50', 'S', 'sh')],
    ['/proc/50/cmdline', Buffer.from('sh\0-c\0arxo-mcp-fide-chess\0')],
    ['/proc/40/stat', procStat(40, 30, '40', 'S', 'npm exec')],
    ['/proc/40/cmdline', Buffer.from('npm exec @arxo/mcp-fide-chess\0')],
    ['/proc/30/stat', procStat(30, 20, '30')],
    ['/proc/30/cmdline', Buffer.from('node\0/usr/lib/node_modules/npm/bin/npx-cli.js\0-y\0package\0')],
    ['/proc/20/stat', procStat(20, 1, '20', 'S', 'unrelated node')],
    ['/proc/20/cmdline', Buffer.from('node\0/client.js\0')],
    ['/proc/1/stat', procStat(1, 0, '1', 'S', 'init')],
    ['/proc/1/cmdline', Buffer.from('/sbin/init\0')],
  ]);
  const read = name => {
    if (!files.has(name)) throw Object.assign(Error('no such process'), { code: 'ENOENT' });
    return files.get(name);
  };
  return { files, read };
}

test('Linux stat parser preserves exact start time and handles parentheses inside the command', () => {
  const identity = parseProcStat(procStat(77, 12, '18446744073709551615', 'S', 'npm exec (chess))'), 77);
  assert.deepEqual(identity, { pid: 77, parentPid: 12, state: 'S', startTime: '18446744073709551615' });
  assert.equal(Object.isFrozen(identity), true);
  for (const raw of [Buffer.from('bad'), procStat(78, 12), procStat(77, -1), procStat(77, 12, 'invalid'), procStat(77, 12, '42', '?')]) {
    assert.throws(() => parseProcStat(raw, 77), /invalid Linux process identity/);
  }
});

test('recognizes npm/npx titles and executable arguments without inspecting /proc/exe', () => {
  for (const command of [
    'npm exec @arxo/mcp-fide-chess\0',
    'npx\0-y\0package\0',
    'node\0--no-opt\0-r\0/proc/.reset\0/usr/local/bin/npx\0--offline\0',
    'node\0/usr/lib/node_modules/npm/bin/npm-cli.js\0exec\0package\0',
    'node\0/usr/lib/node_modules/npm/bin/npx-cli.js\0-y\0package\0',
  ]) assert.equal(isNpmAncestor(Buffer.from(command)), true, command);
  for (const command of ['node\0/client.js\0', 'sh\0-c\0arxo-mcp-fide-chess\0', '/usr/bin/not-npx\0', 'npm-helper\0']) {
    assert.equal(isNpmAncestor(Buffer.from(command)), false, command);
  }
});

test('captures immutable immediate-parent and all npm/npx ancestor identities', () => {
  const f = procFixture(), ancestors = captureLinuxAncestors(100, 50, f.read);
  assert.deepEqual(ancestors.map(p => p.pid), [50, 40, 30]);
  assert.equal(Object.isFrozen(ancestors), true);
  assert.equal(ancestors.every(Object.isFrozen), true);
  assert.equal(linuxAncestorsAlive(ancestors, f.read), true);
  // Non-launcher ancestors are traversed at startup, but do not become shutdown targets or watched identities.
  f.files.delete('/proc/20/stat');
  assert.equal(linuxAncestorsAlive(ancestors, f.read), true);
});

test('npm exec startup refuses a missing npm/npx ancestor even when its shell parent survived', () => {
  const f = procFixture();
  assert.equal(captureLinuxAncestors(100, 50, f.read, true).length, 3);
  f.files.set('/proc/50/stat', procStat(50, 1, '50', 'S', 'sh'));
  assert.deepEqual(captureLinuxAncestors(100, 50, f.read).map(p => p.pid), [50]);
  assert.throws(() => captureLinuxAncestors(100, 50, f.read, true), /npm\/npx ancestor exited/);
  f.files.set('/proc/100/stat', procStat(100, 1));
  assert.throws(() => captureLinuxAncestors(100, 1, f.read, true), /npm\/npx ancestor exited/);
  // Direct exec by npm is also recognized when no intermediate shell exists.
  f.files.set('/proc/100/stat', procStat(100, 40));
  assert.deepEqual(captureLinuxAncestors(100, 40, f.read, true).map(p => p.pid), [40, 30]);
});

test('refuses excessively deep ancestor chains with bounded proc reads', () => {
  let reads = 0;
  const read = name => {
    reads++;
    const [, pidText, type] = name.match(/^\/proc\/([0-9]+)\/(stat|cmdline)$/);
    const pid = Number(pidText);
    return type === 'stat' ? procStat(pid, pid - 1, String(pid)) : Buffer.from('node\0client.js\0');
  };
  assert.throws(() => captureLinuxAncestors(1000, 999, read), /ancestor chain/);
  assert.ok(reads < 200);
});

for (const state of ['Z', 'X', 'x']) {
  test('refuses a ' + state + ' ancestor at startup and during polling', () => {
    const f = procFixture(), ancestors = captureLinuxAncestors(100, 50, f.read);
    f.files.set('/proc/40/stat', procStat(40, 30, '40', state));
    assert.equal(linuxAncestorsAlive(ancestors, f.read), false);
    assert.throws(() => captureLinuxAncestors(100, 50, f.read), /ancestor changed/);
  });
}

test('parent loss, inaccessible proc files and PID reuse fail closed', () => {
  for (const change of [
    f => f.files.delete('/proc/50/stat'),
    f => f.files.set('/proc/50/stat', procStat(50, 40, '51')),
    f => f.files.set('/proc/40/stat', procStat(40, 30, '41')),
  ]) {
    const f = procFixture(), ancestors = captureLinuxAncestors(100, 50, f.read);
    change(f);
    assert.equal(linuxAncestorsAlive(ancestors, f.read), false);
  }
  const f = procFixture(), ancestors = captureLinuxAncestors(100, 50, f.read);
  assert.equal(linuxAncestorsAlive(ancestors, () => { throw Object.assign(Error('denied'), { code: 'EACCES' }); }), false);
});

test('startup rejects reparenting, a disappearing ancestor, PID reuse and ancestor cycles', () => {
  const reparented = procFixture();
  reparented.files.set('/proc/100/stat', procStat(100, 1));
  assert.throws(() => captureLinuxAncestors(100, 50, reparented.read), /parent changed/);
  const gone = procFixture();
  gone.files.delete('/proc/40/stat');
  assert.throws(() => captureLinuxAncestors(100, 50, gone.read), /no such process/);
  const cyclic = procFixture();
  cyclic.files.set('/proc/20/stat', procStat(20, 40, '20'));
  assert.throws(() => captureLinuxAncestors(100, 50, cyclic.read), /ancestor chain/);
  for (const replacement of [procStat(50, 40, '51'), procStat(100, 1)]) {
    const raced = procFixture();
    let reads = 0;
    const racedPath = replacement.toString().startsWith('50 ') ? '/proc/50/stat' : '/proc/100/stat';
    const read = name => name === racedPath && ++reads === 2 ? replacement : raced.read(name);
    assert.throws(() => captureLinuxAncestors(100, 50, read), /ancestor changed/);
  }
});

test('ancestor watcher calls only the own-child shutdown callback once when the parent dies', async t => {
  const f = procFixture(), ancestors = captureLinuxAncestors(100, 50, f.read);
  let notifications = 0, stop;
  const completed = new Promise((resolve, reject) => {
    const deadline = setTimeout(() => reject(Error('ancestor watcher did not detect parent exit')), 1500);
    t.after(() => clearTimeout(deadline));
    stop = watchLinuxAncestors(ancestors, () => { notifications++; clearTimeout(deadline); resolve(); }, f.read);
  });
  t.after(() => stop());
  f.files.set('/proc/50/stat', procStat(50, 40, '50', 'Z'));
  await completed;
  stop();
  await new Promise(resolve => setTimeout(resolve, 300));
  assert.equal(notifications, 1);
});

test('ancestor watcher detects startup races immediately and can be stopped without a callback', async () => {
  const f = procFixture(), ancestors = captureLinuxAncestors(100, 50, f.read);
  let notifications = 0;
  const stop = watchLinuxAncestors(ancestors, () => notifications++, f.read);
  stop();
  f.files.delete('/proc/50/stat');
  await new Promise(resolve => setTimeout(resolve, 300));
  assert.equal(notifications, 0);
  const stopAlreadyDead = watchLinuxAncestors(ancestors, () => notifications++, f.read);
  assert.equal(notifications, 1);
  stopAlreadyDead();
});
