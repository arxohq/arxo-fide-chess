/** Build only from pinned public canon bytes; never lower the live corpus. */
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const pkg = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const pin = JSON.parse(fs.readFileSync(path.join(pkg, 'source-pin.json')));
const at = process.argv.indexOf('--canon');
const canon = at < 0 ? null : path.resolve(process.argv[at + 1]);
const sha = bytes => `sha256:${createHash('sha256').update(bytes).digest('hex')}`;
for (const [target, asset] of Object.entries(pin.derivedFixtures)) {
  const bytes = fs.readFileSync(path.join(pkg, target));
  if (bytes.length !== asset.bytes || sha(bytes) !== asset.sha256) throw new Error(`Captured fixture mismatch: ${target}`);
}
for (const [target, asset] of Object.entries(pin.files)) {
  const from = canon ? path.join(canon, asset.from) : path.join(pkg, target);
  const bytes = fs.readFileSync(from);
  if (bytes.length !== asset.bytes || sha(bytes) !== asset.sha256) throw new Error(`Pinned asset mismatch: ${asset.from}`);
  if (canon) {
    fs.mkdirSync(path.dirname(path.join(pkg, target)), { recursive: true });
    fs.writeFileSync(path.join(pkg, target), bytes);
  }
}
const write = (relative, bytes) => {
  fs.mkdirSync(path.dirname(path.join(pkg, relative)), { recursive: true });
  fs.writeFileSync(path.join(pkg, relative), bytes);
};
const quote = JSON.stringify;
write('models.json', `${JSON.stringify(pin.models, null, 2)}\n`);
const specs = pin.models.map(row => quote(row.spec)).join(' | ');
write('index.d.ts', `import type {} from './types/registry.js';
export type ModelSpec = ${specs};
export interface ModelInfo {
  readonly spec: ModelSpec; readonly name: string; readonly version: string;
  readonly subpath: string; readonly namespace: string;
  readonly worldHash: string; readonly packageHash: string; readonly languageSemantics: string;
  readonly questionCatalogHash: string | null;
}
export interface ModelPin {
  readonly repository: string; readonly revision: string;
  readonly modelHash: string; readonly worldHash: string; readonly languageSemantics: string;
}
export interface LoadedModel<S extends ModelSpec = ModelSpec> {
  readonly spec: S;
  readonly package: { readonly ir: unknown; readonly meta: {
    readonly name: string; readonly version: string; readonly namespace: string;
    readonly contentHash: string; readonly packageContentHash: string;
    readonly canon: { readonly repository: string; readonly revision: string };
  } };
  readonly descriptor: Readonly<Record<string, unknown>>;
  readonly pin: ModelPin;
  readonly questionCatalog?: unknown;
}
export declare const models: readonly ModelInfo[];
export declare class ModelNotFoundError extends Error { readonly code: 'MODEL_NOT_FOUND'; readonly spec: unknown; }
export declare class ModelIntegrityError extends Error {
  readonly code: 'MODEL_INTEGRITY'; readonly spec: string; readonly asset: string;
  readonly expected: string; readonly actual: string;
}
export declare function loadModel<S extends ModelSpec>(spec: S): Promise<LoadedModel<S>>;
`);
let declarations = `import type {} from '@arxo/law';\n\ndeclare module '@arxo/law' {\n  interface CanonRegistry {\n`;
for (const model of pin.models) {
  const base = path.join(pkg, 'data', model.subpath);
  const descriptor = JSON.parse(fs.readFileSync(path.join(base, 'descriptor.json')));
  const ir = JSON.parse(fs.readFileSync(path.join(base, 'package.lawir.json')));
  const world = JSON.parse(fs.readFileSync(path.join(base, 'world.lawir.json')));
  const semantics = value => `law.core/${value}`.replace('law.core/law.core/', 'law.core/');
  if (descriptor.worldHash !== model.worldHash || descriptor.contentHash !== model.packageHash
      || descriptor.name !== model.name || descriptor.version !== model.version
      || descriptor.namespace !== model.namespace || descriptor.languageSemantics !== model.languageSemantics
      || (descriptor.questionCatalogHash ?? null) !== model.questionCatalogHash
      || [ir.package, world.package].some(p => p.name !== model.name || p.version !== model.version || p.namespace !== model.namespace)
      || [ir, world].some(p => semantics(p.semanticVersion) !== model.languageSemantics)
      || sha(fs.readFileSync(path.join(base, 'package.lawir.json'))) !== descriptor.contentHash
      || sha(fs.readFileSync(path.join(base, 'world.lawir.json'))) !== descriptor.worldHash) throw new Error(`Model pin mismatch: ${model.spec}`);
  for (const dependency of descriptor.dependencies) {
    const imported = world.imports.find(row => row.package?.name === dependency.name);
    if (!imported || imported.package.version !== dependency.version || imported.package.namespace !== dependency.namespace) throw new Error(`Import closure mismatch: ${model.spec} -> ${dependency.name}`);
  }
  write(`src/${model.subpath}.js`, `import { loadModel as load } from './index.js';\nexport const spec = ${quote(model.spec)};\nexport function loadModel() { return load(spec); }\n`);
  write(`types/${model.subpath}.d.ts`, `import type { LoadedModel } from '../index.js';\nexport declare const spec: ${quote(model.spec)};\nexport declare function loadModel(): Promise<LoadedModel<typeof spec>>;\n`);
  const relations = (ir.nodes ?? []).filter(n => n.kind === 'symbol_decl' && n.symbolKind === 'relation');
  const namespaces = new Map([world.package, ...(world.imports ?? []).map(row => row.package)]
    .filter(Boolean).map(p => [p.namespace, p.name]));
  const qualified = (world.nodes ?? []).filter(n => n.kind === 'symbol_decl' && n.symbolKind === 'relation')
    .map(n => { const [ns, local] = n.id.split('#'); return namespaces.has(ns) ? [`${namespaces.get(ns)}::${local}`, n.id] : null; }).filter(Boolean);
  declarations += `    ${quote(model.name)}: {\n      readonly relations: {\n`;
  for (const n of relations.sort((a,b) => a.id.localeCompare(b.id))) declarations += `        readonly ${quote(n.name ?? n.id.split('#')[1])}: ${quote(n.id)};\n`;
  declarations += `      };\n      readonly qualifiedRelations: {\n`;
  for (const [name, id] of qualified.sort((a,b) => a[0].localeCompare(b[0]))) declarations += `        readonly ${quote(name)}: ${quote(id)};\n`;
  declarations += `      };\n    };\n`;
}
declarations += '  }\n}\n';
write('types/registry.d.ts', declarations);
console.log(`canon-fide-chess: ${pin.models.length} pinned models; Node entries and declarations generated`);
