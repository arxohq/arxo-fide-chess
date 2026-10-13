/** Prepare one immutable candidate using the established delivery manifest. */
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const args = process.argv.slice(2);
if (args.length !== 2 || args[0] !== '--out') throw Error('Usage: node tools/prepare-candidate.mjs --out NEW_DIRECTORY_OUTSIDE_GIT');
const out = resolve(args[1]);
const rel = relative(resolve(root, '..'), out);
if (!rel.startsWith('..') || existsSync(out)) throw Error('Use a new directory outside the canon checkout');
execFileSync(process.execPath, ['tools/build.mjs', '--canon', '..'], { cwd: root, stdio: 'inherit' });
mkdirSync(out, { recursive: true });
const packed = JSON.parse(execFileSync('npm', ['pack', '--ignore-scripts', '--json', '--pack-destination', out], {
  cwd: root, encoding: 'utf8',
}))[0];
const bytes = readFileSync(join(out, packed.filename));
const manifest = { schema: 'arxo.npm-candidate/1', status: 'PREPARED_WITH_DEFERRED_VERIFICATION',
  published: false, releaseVerified: false, corpus: 'not_checked',
  note: 'Only the FIDE chess Node.js demonstration. Addressed source, SDK and installed-consumer checks are separate from full subject acceptance.',
  requiredPublishedDependencies: { '@arxo/law': '0.4.3' },
  packages: [{ name: packed.name, file: packed.filename, bytes: bytes.length,
    sha256: createHash('sha256').update(bytes).digest('hex') }],
};
writeFileSync(join(out, 'facade-npm.json'), JSON.stringify(manifest, null, 2) + '\n');
writeFileSync(join(out, 'inventory.json'), JSON.stringify(packed.files, null, 2) + '\n');
console.log(JSON.stringify(manifest, null, 2));
