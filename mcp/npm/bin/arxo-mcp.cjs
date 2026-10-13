#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const crypto = require('node:crypto');
const { spawn } = require('node:child_process');
const PIN_SHA256 = '__PIN_SHA256__'; // Fixed by the packer after the raw-byte pin is written.
const PACKAGE = '@arxo/mcp-fide-chess';

function sha(raw) {
  return 'sha256:' + crypto.createHash('sha256').update(raw).digest('hex');
}
function canonical(value) {
  if (Array.isArray(value)) return '[' + value.map(canonical).join(',') + ']';
  if (value && typeof value === 'object') {
    return '{' + Object.keys(value).sort().map(k => JSON.stringify(k) + ':' + canonical(value[k])).join(',') + '}';
  }
  return JSON.stringify(value);
}
function verifySlice(root, pin) {
  if (!fs.lstatSync(root).isDirectory() || fs.lstatSync(root).isSymbolicLink()) throw Error('slice must be a real directory');
  const entries = pin.data.entries;
  if (sha(Buffer.from(canonical(entries))) !== pin.data.treeSha256) throw Error('data inventory digest mismatch');
  const expected = new Map();
  for (const row of entries) {
    if (!row.path || row.path.includes('\\') || row.path.startsWith('/') || row.path.split('/').some(p => !p || p === '.' || p === '..')) {
      throw Error('unsafe pinned data path');
    }
    if (expected.has(row.path) || !['file', 'directory'].includes(row.type)) throw Error('invalid data inventory');
    expected.set(row.path, row);
  }
  let count = 0;
  function walk(dir, prefix) {
    for (const name of fs.readdirSync(dir)) {
      const rel = prefix + name, full = path.join(dir, name), st = fs.lstatSync(full);
      const row = expected.get(rel);
      if (!row || st.isSymbolicLink()) throw Error('unexpected data entry: ' + rel);
      count++;
      if (row.type === 'directory') {
        if (!st.isDirectory()) throw Error('wrong data type: ' + rel);
        walk(full, rel + '/');
      } else {
        if (!st.isFile() || st.size !== row.size || sha(fs.readFileSync(full)) !== row.sha256) throw Error('altered data file: ' + rel);
        if ((st.mode & 0o111) !== 0) throw Error('executable data file: ' + rel);
      }
    }
  }
  walk(root, '');
  if (count !== expected.size) throw Error('missing pinned data entry');
}
function verifyInstallation(packageRoot) {
  const bytes = fs.readFileSync(path.join(packageRoot, 'pin.json'));
  if (sha(bytes) !== PIN_SHA256) throw Error('pin.json differs from the accepted launcher pin');
  const pin = JSON.parse(bytes);
  if (pin.format !== 'arxo.mcp-npm-pin/0.1' || pin.profile !== 'fide-chess') throw Error('unsupported FIDE chess pin');
  const platform = process.platform + '-' + process.arch;
  const host = pin.binaries[platform];
  if (!host) throw Error('unsupported platform ' + platform + '; supported: ' + Object.keys(pin.binaries).join(', ') + '. Hosted endpoint: https://mcp.arxo.io/mcp/fide-chess');
  let binary, hostPackage;
  try {
    binary = require.resolve(host.package + '/bin/law-mcp-server', { paths: [packageRoot] });
    hostPackage = JSON.parse(fs.readFileSync(require.resolve(host.package + '/package.json', { paths: [packageRoot] })));
  } catch {
    throw Error('missing ' + host.package + '@' + host.version + '; reinstall without --omit=optional');
  }
  if (hostPackage.name !== host.package || hostPackage.version !== host.version || sha(fs.readFileSync(binary)) !== host.sha256) {
    throw Error('shared host version/binary differs from the accepted pin; reinstall ' + PACKAGE);
  }
  fs.accessSync(binary, fs.constants.X_OK);
  const slice = path.join(packageRoot, 'slice');
  verifySlice(slice, pin);
  return { pin, binary, slice };
}
function main() {
  const packageRoot = path.resolve(__dirname, '..');
  const args = process.argv.slice(2);
  if (args.length === 1 && args[0] === '--help') {
    console.log('Run pinned FIDE chess MCP over stdio: npx -y @arxo/mcp-fide-chess@0.1.0\nNode.js 20+, Linux x64 or macOS arm64. No server arguments are forwarded.\nHosted endpoint: https://mcp.arxo.io/mcp/fide-chess');
    return;
  }
  if (args.length === 1 && args[0] === '--version') {
    console.log(PACKAGE + '@' + JSON.parse(fs.readFileSync(path.join(packageRoot, 'package.json'))).version);
    return;
  }
  if (args.length) throw Error('only --help or --version is accepted; start without arguments for stdio');
  const timeout = process.env.FIDE_CHESS_MCP_CALL_TIMEOUT || '30';
  if (!/^[1-9][0-9]*$/.test(timeout) || Number(timeout) > 110) throw Error('FIDE_CHESS_MCP_CALL_TIMEOUT must be an integer from 1 to 110');
  const { binary, slice } = verifyInstallation(packageRoot);
  const state = fs.mkdtempSync(path.join(os.tmpdir(), 'arxo-fide-chess-mcp-'));
  fs.chmodSync(state, 0o700);
  let cleaned = false;
  function cleanup() {
    if (!cleaned) { cleaned = true; fs.rmSync(state, { recursive: true, force: true }); }
  }
  process.on('exit', cleanup);
  const child = spawn(binary, ['--root', slice, '--profile', 'fide-chess'], {
    stdio: 'inherit',
    env: {
      PATH: '/usr/bin:/bin', HOME: state, TMPDIR: state, LANG: 'C.UTF-8',
      LAW_MCP_ARTIFACT_DIR: path.join(state, 'artifacts'), LAW_MCP_LOG: '0',
      LAW_MCP_CALL_TIMEOUT: timeout,
    },
  });
  let requestedSignal, timer;
  for (const signal of ['SIGINT', 'SIGTERM', 'SIGHUP']) {
    process.on(signal, () => {
      requestedSignal = signal;
      child.kill(signal);
      if (!timer) timer = setTimeout(() => { child.kill('SIGKILL'); cleanup(); process.exit(128 + os.constants.signals[signal]); }, 5000);
    });
  }
  child.on('error', error => { console.error(PACKAGE + ': ' + error.message); cleanup(); process.exit(2); });
  child.on('exit', (code, signal) => {
    if (timer) clearTimeout(timer);
    cleanup();
    process.exit(code ?? (128 + (os.constants.signals[signal || requestedSignal] || 1)));
  });
}
if (require.main === module) {
  try { main(); } catch (error) { console.error(PACKAGE + ': ' + error.message); process.exitCode = 2; }
}
module.exports = { sha, canonical, verifySlice, verifyInstallation };
