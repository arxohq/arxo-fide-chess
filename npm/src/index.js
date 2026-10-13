/** Node-only loading of frozen canon bytes. Execution belongs to @arxo/law. */
import { readFileSync } from 'node:fs';
import { readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';

const root = new URL('../', import.meta.url);
const source = JSON.parse(readFileSync(new URL('source-pin.json', root), 'utf8'));
const catalog = JSON.parse(readFileSync(new URL('models.json', root), 'utf8'));
export const models = Object.freeze(catalog.map(row => Object.freeze({ ...row })));
const bySpec = new Map(models.map(row => [row.spec, row]));
const sha = bytes => `sha256:${createHash('sha256').update(bytes).digest('hex')}`;

export class ModelNotFoundError extends Error {
  constructor(spec) {
    const label = typeof spec === 'string' ? JSON.stringify(spec) : `<${spec === null ? 'null' : typeof spec}>`;
    super(`Model ${label} is not in this pinned FIDE chess release; choose an exact spec from models.`);
    this.name = 'ModelNotFoundError';
    this.code = 'MODEL_NOT_FOUND';
    this.spec = spec;
  }
}

export class ModelIntegrityError extends Error {
  constructor(spec, asset, expected, actual, cause) {
    super(`Model ${spec}: ${asset} does not match its pinned bytes`, { cause });
    this.name = 'ModelIntegrityError';
    this.code = 'MODEL_INTEGRITY';
    Object.assign(this, { spec, asset, expected, actual });
  }
}

async function checked(spec, asset, expected) {
  let bytes;
  try {
    bytes = await readFile(new URL(asset, root));
  } catch (cause) {
    throw new ModelIntegrityError(spec, asset, expected, 'unreadable', cause);
  }
  const actual = sha(bytes);
  if (actual !== expected || bytes.length !== source.files[asset]?.bytes) throw new ModelIntegrityError(spec, asset, expected, actual);
  return bytes;
}

/** Fresh, isolated JSON per call; only the requested world is read and parsed. */
export async function loadModel(spec) {
  const model = bySpec.get(spec);
  if (!model) throw new ModelNotFoundError(spec);
  const base = `data/${model.subpath}`;
  const descriptorPath = `${base}/descriptor.json`;
  const descriptor = JSON.parse(await checked(spec, descriptorPath, source.files[descriptorPath].sha256));
  const worldBytes = await checked(spec, `${base}/world.lawir.json`, model.worldHash);
  if (descriptor.worldHash !== model.worldHash || descriptor.contentHash !== model.packageHash
      || descriptor.name !== model.name || descriptor.version !== model.version
      || descriptor.namespace !== model.namespace || descriptor.languageSemantics !== model.languageSemantics
      || (descriptor.questionCatalogHash ?? null) !== model.questionCatalogHash) {
    throw new ModelIntegrityError(spec, descriptorPath, model.worldHash, descriptor.worldHash);
  }
  // Integrity is checked over the original world bytes BEFORE JSON.parse.
  const ir = JSON.parse(worldBytes);
  if (ir.package?.name !== model.name || ir.package?.version !== model.version || ir.package?.namespace !== model.namespace
      || `law.core/${ir.semanticVersion}`.replace('law.core/law.core/', 'law.core/') !== model.languageSemantics) {
    throw new ModelIntegrityError(spec, `${base}/world.lawir.json`, model.spec, 'world identity mismatch');
  }
  let questionCatalog;
  if (descriptor.questionCatalogHash) {
    const digest = descriptor.questionCatalogHash.replace(/^sha256:/, '');
    questionCatalog = JSON.parse(await checked(spec, `data/resources/${digest}.json`, descriptor.questionCatalogHash));
  }
  const pin = Object.freeze({
    repository: source.repository,
    revision: source.revision,
    modelHash: model.packageHash,
    worldHash: model.worldHash,
    languageSemantics: model.languageSemantics,
  });
  // Keep the original registry descriptor separate: its contentHash is the
  // PACKAGE hash. The facade's canon metadata contentHash is the WORLD hash.
  const meta = Object.freeze({
    name: model.name, version: model.version, namespace: model.namespace,
    contentHash: model.worldHash, packageContentHash: model.packageHash,
    canon: Object.freeze({ repository: source.repository, revision: source.revision }),
  });
  return Object.freeze({
    spec: model.spec,
    package: Object.freeze({ ir, meta }),
    descriptor: Object.freeze(descriptor),
    pin,
    ...(questionCatalog === undefined ? {} : { questionCatalog }),
  });
}
