import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { open } from '@arxo/law';
import { models, loadModel } from '@arxo/canon-fide-chess';
import { spec, loadModel as loadChess } from '@arxo/canon-fide-chess/chess';
import { caseNames, game, white, king, getCaseInput } from '@arxo/canon-fide-chess/examples/arbiter';

const model = await loadChess();
const chess = await open(model.spec, { offline: true, local: { packages: { [model.spec]: model.package } } });
const expected = JSON.parse(readFileSync(new URL('./expectations.json', import.meta.url)));
const queries = JSON.parse(readFileSync(new URL('./queries.json', import.meta.url)));
const doc = answer => JSON.parse(new TextDecoder().decode(answer.document));

test('exact entry, descriptor, package/world metadata and referenced catalog', async () => {
  assert.equal(spec, 'fide.laws.chess@0.1.1');
  assert.equal(models.length, 1);
  assert.deepEqual((await loadModel(spec)).descriptor, model.descriptor);
  assert.equal(model.package.meta.contentHash, model.pin.worldHash);
  assert.equal(model.package.meta.packageContentHash, model.descriptor.contentHash);
  assert.equal(model.descriptor.languageSemantics, 'law.core/0.2.11');
  assert.equal(model.questionCatalog.package, 'fide.laws.chess');
  assert.deepEqual(model.descriptor.dependencies, []);
  assert(chess.unfold('must_move_first_touched_piece', { depth: 2 }).tree);
});

test('all eighteen retained case/query expectations, including required producer rules', async () => {
  assert.equal(caseNames.length, 10);
  for (const item of expected) {
    const query = queries[item.query.split('/').pop()];
    const answer = await chess.truth(query.literal.predicate,
      query.literal.args.map(term => term.id ?? term.value), getCaseInput(item.case));
    const label = `${item.case} / ${item.query}`;
    assert.equal(answer.evaluationStatus, item.evaluationStatus, label);
    if (item.truthStatus) assert.equal(answer.truthStatus, item.truthStatus, label);
    for (const rule of item.requiredRules ?? []) {
      assert(answer.proof.nodes.some(node => JSON.stringify(node).includes(rule)), `${label}: ${rule}`);
    }
    if (item.judgmentRequired) assert(doc(answer).results[0].judgmentRequests.length > 0, label);
  }
});

test('fixtures are independent and preserve absent judgments', () => {
  const a = getCaseInput('SecondIllegal');
  a.assertions.length = 0;
  assert(getCaseInput('SecondIllegal').assertions.length > 0);
  assert.throws(() => getCaseInput('NotACase'), RangeError);
  const touch = getCaseInput('TouchIntentUnknown');
  assert(!touch.assertions.some(a => a.literal.predicate.endsWith('#piece_touched_intentionally')));
});

test('an explicit adjudicated touch judgment establishes the obligation', async () => {
  const input = getCaseInput('TouchIntentUnknown');
  const assertion = structuredClone(input.assertions[0]);
  assertion.id += '-touch-intent';
  assertion.origin = 'adjudicated';
  delete assertion.contentHash;
  assertion.literal = { kind: 'literal', polarity: 'positive',
    predicate: 'urn:fide:laws:clir:chess#piece_touched_intentionally',
    args: [{ kind: 'entity_ref', id: white }, { kind: 'entity_ref', id: king }] };
  input.assertions.push(assertion);
  const answer = await chess.truth('must_move_first_touched_piece', [white, king], input);
  assert.equal(answer.evaluationStatus, 'COMPUTED');
  assert.equal(answer.truthStatus, 'TRUE_ONLY');
  assert(!getCaseInput('TouchIntentUnknown').assertions.some(a => a.origin === 'adjudicated'));
});

test('missing, negative and conflicting empirical facts keep four-valued statuses', async () => {
  const context = { legalTime: '2023-06-01', decisionTime: '2026-09-08T12:00:00Z',
    knowledgeTime: '2026-09-08T12:00:00Z', timezone: 'UTC' };
  const fact = state => ({ predicate: 'player_resigned', args: [white], state });
  const missing = await chess.truth('player_resigned', [white], context);
  const negative = await chess.truth('player_resigned', [white], { ...context, answers: [fact('no')] });
  const conflict = await chess.truth('player_resigned', [white], { ...context, answers: [fact('yes'), fact('no')] });
  assert.equal(missing.truthStatus, 'NEITHER');
  assert.equal(negative.truthStatus, 'FALSE_ONLY');
  assert.equal(conflict.truthStatus, 'BOTH');
  assert.equal(conflict.evaluationStatus, 'COMPUTED');
});

test('half-point boundaries execute the repaired Decimal path without errors', async () => {
  for (const [value, truth] of [[0, 'NEITHER'], [0.25, 'TRUE_ONLY'], [0.5, 'NEITHER'],
    [0.75, 'TRUE_ONLY'], [1, 'NEITHER'], [1.5, 'NEITHER']]) {
    const answer = await chess.truth('recorded_score_not_normally_associated', [game, white], {
      legalTime: '2026-09-01', decisionTime: '2026-09-01T12:00:00Z',
      knowledgeTime: '2026-09-01T12:00:00Z', timezone: 'UTC',
      answers: [{ predicate: 'points_recorded', args: [game, white, String(value)] }],
    });
    assert.equal(answer.evaluationStatus, 'COMPUTED', String(value));
    assert.equal(answer.truthStatus, truth, String(value));
    assert(!doc(answer).issues.some(issue => issue.severity === 'error'), String(value));
  }
});

test('identical explicit inputs reproduce canonical document and evaluation hashes', async () => {
  const input = getCaseInput('SecondIllegal');
  const first = await chess.truth('game_lost_by', [game, white], input);
  const second = await chess.truth('game_lost_by', [game, white], input);
  assert.deepEqual(first.hashes, second.hashes);
  assert.deepEqual(first.document, second.document);
  assert(first.proof.nodes.length > 0);
  // SDK 0.4.3 emits producer IDs, while its source-anchor arrays are empty.
  // Verify the separate static source link in the retained, hash-checked model.
  const application = first.proof.nodes.find(node => node.rule?.endsWith('#SecondIllegalMoveLoses'));
  const rule = model.package.ir.nodes.find(node => node.id === application.rule);
  assert(rule.anchors.includes('urn:fide:laws:clir:chess#FIDE_ART_7'));
  assert.equal(first.sources.length, 0);
});
