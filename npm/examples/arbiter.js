import { readFileSync } from 'node:fs';
const fixtures = JSON.parse(readFileSync(new URL('./arbiter-cases.json', import.meta.url), 'utf8'));
export const caseNames = Object.freeze(Object.keys(fixtures));
export const game = 'urn:example:chess:game';
export const white = 'urn:example:chess:white';
export const black = 'urn:example:chess:black';
export const king = 'urn:example:chess:king';
export function getCaseInput(name) {
  if (!Object.hasOwn(fixtures, name)) throw new RangeError(`Unknown arbiter case: ${String(name)}`);
  return structuredClone(fixtures[name]);
}
