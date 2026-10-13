/** Figures are derived from the admitted model and SDK answers; no chess evaluator here. */
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { open } from '@arxo/law';
import { loadModel } from '../src/chess.js';
import { game, white, king, getCaseInput } from '../examples/arbiter.js';

const model = await loadModel();
const chess = await open(model.spec, { offline: true, local: { packages: { [model.spec]: model.package } } });
const assets = new URL('../assets/', import.meta.url);
mkdirSync(assets, { recursive: true });
const write = (name, bytes) => writeFileSync(new URL(name, assets), bytes);
const nodes = new Map(model.package.ir.nodes.map(node => [node.id, node]));
const records = [];
for (const name of ['SecondIllegal', 'SecondIllegalNoMate']) {
  const input = getCaseInput(name);
  const loss = await chess.truth('game_lost_by', [game, white], input);
  const draw = await chess.truth('game_drawn', [game], input);
  assert.equal(draw.truthStatus, name === 'SecondIllegalNoMate' ? 'TRUE_ONLY' : 'NEITHER');
  assert.equal(loss.truthStatus, name === 'SecondIllegal' ? 'TRUE_ONLY' : 'NEITHER');
  const summary = answer => ({ evaluationStatus: answer.evaluationStatus, truthStatus: answer.truthStatus,
    hashes: answer.hashes, proofNodes: answer.proof.nodes.length,
    judgmentRequests: JSON.parse(new TextDecoder().decode(answer.document)).results[0].judgmentRequests,
    producerRules: [...new Set(answer.proof.nodes.filter(node => node.rule).map(node => node.rule))],
    modelAnchorLinks: answer.proof.nodes.filter(node => node.rule).map(node => ({
      rule: node.rule, anchors: (nodes.get(node.rule)?.anchors ?? []).map(id => ({ id, locator: nodes.get(id)?.locator })),
    })),
  });
  records.push({ name, legalTime: input.legalTime, loss: summary(loss), draw: summary(draw) });
}
const touch = await chess.truth('must_move_first_touched_piece', [white, king], getCaseInput('TouchIntentUnknown'));
assert.equal(touch.evaluationStatus, 'REQUIRES_JUDGMENT');
const unfold = chess.unfold('must_move_first_touched_piece', { depth: 2, lang: 'en', quote: 0 });
write('touch-unfold.json', JSON.stringify(unfold, null, 2) + '\n');
write('example-evidence.json', JSON.stringify({ format: 'arxo.fide-chess-readme-evidence/1', spec: model.spec,
  worldHash: model.pin.worldHash, sdk: '@arxo/law@0.4.3', engine: '@arxo/law-engine@0.5.3',
  sourceLinks: 'Static join of executed producer IDs with anchors in the pinned model; SDK source arrays are empty.',
  cases: records, touch: { evaluationStatus: touch.evaluationStatus, truthStatus: touch.truthStatus,
    judgmentRequests: JSON.parse(new TextDecoder().decode(touch.document)).results[0].judgmentRequests, hashes: touch.hashes },
}, null, 2) + '\n');

const C = { cream: '#f8f4eb', ink: '#122d4c', muted: '#53677d', blue: '#315d84',
  green: '#14644b', greenSoft: '#e6f1eb', amber: '#875617', amberSoft: '#fbefd9' };
const esc = value => String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');
const text = (x, y, value, size = 22, color = C.ink, weight = 400, mono = false) =>
  `<text x="${x}" y="${y}" font-size="${size}" font-weight="${weight}" fill="${color}"${mono ? ' class="mono"' : ''}>${esc(value)}</text>`;
const box = (x, y, w, h, color) => `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="16" fill="${color}"/>`;
const arrow = (x1, y1, x2, y2) => `<path d="M${x1} ${y1} L${x2} ${y2}" stroke="${C.blue}" stroke-width="2" marker-end="url(#arrow)"/>`;
const svg = (w, h, title, desc, body) => `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" role="img" aria-labelledby="title desc"><title id="title">${esc(title)}</title><desc id="desc">${esc(desc)}</desc><style>text{font-family:Arial,Helvetica,sans-serif}.mono{font-family:Menlo,Consolas,monospace}</style><defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8" fill="${C.blue}"/></marker></defs>${box(0, 0, w, h, C.cream)}${body.join('\n')}</svg>\n`;

const board = [];
for (let rank = 0; rank < 4; rank++) for (let file = 0; file < 4; file++) {
  board.push(`<rect x="${835 + file * 66}" y="${140 + rank * 66}" width="66" height="66" fill="${(file + rank) % 2 ? '#315d84' : '#dbe5ee'}"/>`);
}
write('cover.svg', svg(1200, 620, 'FIDE Laws of Chess on Arxo', 'A pinned chess-arbiter model, ten retained cases and inspectable answers. Independent Node.js teaching demonstration.', [
  text(54, 67, 'ARXO  /  EXECUTABLE MODELS', 19, C.muted, 650),
  text(54, 169, 'FIDE Laws of Chess', 58, C.ink, 750),
  text(54, 241, 'on Arxo', 58, C.ink, 750),
  text(57, 303, 'Facts. Exceptions. Arbiter judgment. Proof.', 26, C.muted),
  box(54, 352, 660, 67, '#e8ecef'), text(79, 396, 'Node.js 20+  /  @arxo/law 0.4.3', 24, C.blue, 600, true),
  text(57, 489, '10 retained arbiter cases', 29, C.ink, 700),
  text(57, 534, '18 checked questions · pinned 2023 edition', 23, C.muted),
  ...board, box(820, 434, 297, 83, C.greenSoft), text(844, 467, 'SECOND ILLEGAL MOVE', 15, C.green, 650, true),
  text(844, 499, records[0].loss.truthStatus, 26, C.green, 700, true),
  text(56, 588, 'INDEPENDENT OPEN-SOURCE TEACHING DEMONSTRATION · MODEL 0.1.1', 16, C.muted, 600),
]));
write('model-to-answer.svg', svg(1000, 560, 'From an episode to an inspectable answer', 'A frozen model and explicit case facts enter the common Arxo SDK. Loss and draw are separate questions. The canonical answer records producer rules and judgments.', [
  text(36, 54, 'A recorded episode, evaluated by the model.', 31, C.ink, 700),
  box(36, 90, 292, 120, '#e8ecef'), text(58, 128, 'loadModel()', 25, C.blue, 650, true),
  text(58, 164, 'fide.laws.chess@0.1.1', 19, C.ink, 400, true), text(58, 192, 'Original bytes checked', 19, C.muted),
  box(360, 90, 604, 120, '#e8ecef'), text(382, 128, "getCaseInput('SecondIllegal')", 23, C.blue, 650, true),
  text(382, 164, 'Explicit facts · date · any arbiter judgments', 21), text(382, 192, 'No judgment is supplied by the loader', 19, C.muted),
  arrow(182, 218, 182, 252), arrow(660, 218, 660, 252),
  box(36, 260, 928, 86, '#dce6ef'), text(58, 296, '@arxo/law → open(... local.packages)', 24, C.blue, 650, true),
  text(58, 325, 'Offline WebAssembly execution · rules and exceptions remain in the model', 19, C.muted),
  arrow(269, 354, 269, 387), arrow(736, 354, 736, 387),
  box(36, 397, 446, 124, C.greenSoft), box(518, 397, 446, 124, '#e8ecef'),
  text(58, 433, 'game_lost_by(game, white)', 21, C.green, 650, true),
  text(58, 477, records[0].loss.truthStatus, 29, C.green, 700, true), text(58, 508, records[0].loss.evaluationStatus, 18, C.green, 600, true),
  text(540, 433, 'Canonical document + proof', 24, C.blue, 650),
  text(540, 475, 'Producer IDs · requests · hashes', 20, C.ink), text(540, 508, 'Source links join the retained model anchors', 17, C.muted),
]));
write('loss-and-exception.svg', svg(1000, 470, 'The exception changes the result', 'Both cases contain two illegal moves. An explicit inability to checkmate changes the established conclusion from loss to draw. A separate loss query may still require judgments for other reachable grounds.', [
  text(38, 56, 'The same incident. One explicit exception.', 32, C.ink, 700),
  ...records.flatMap((record, index) => {
    const x = 38 + index * 480;
    return [box(x, 88, 444, 336, index ? C.amberSoft : C.greenSoft),
      text(x + 23, 131, record.name, 22, C.ink, 650, true),
      text(x + 23, 177, 'Two completed illegal moves', 22),
      text(x + 23, 217, index ? 'Opponent cannot checkmate' : 'No inability-to-mate exception', 20, C.muted),
      text(x + 23, 276, index ? 'DRAW' : 'LOSS', 44, index ? C.amber : C.green, 750),
      text(x + 23, 318, index ? record.draw.truthStatus : record.loss.truthStatus, 24, index ? C.amber : C.green, 650, true),
      text(x + 23, 359, index ? 'Article 7.5.5 · explicit exception' : 'Article 7.5.5 · model conclusion', 19, C.muted),
      text(x + 23, 398, index ? 'Loss query: judgment for other grounds' : 'Proof names SecondIllegalMoveLoses', 16, C.muted)];
  }),
]));
const rows = [];
function visit(node, depth = 0, producer = false) {
  rows.push({ depth, producer, role: producer ? node.strength : node.relationKind === 'judgment' ? 'judgment' : node.relationKind === 'empirical' ? 'fact' : 'derived', name: node.name ?? node.kind ?? 'test',
    prefix: producer ? '⇐ ' : node.polarity === 'negative' ? 'not ' : '', anchor: node.anchors?.[0]?.locator ?? '' });
  for (const child of node.producers ?? []) visit(child, depth + 1, true);
  for (const child of node.premises ?? []) visit(child, depth + 1);
}
visit(unfold.tree);
const visible = rows.slice(1, 57);
write('knows-touch.svg', svg(1100, 175 + visible.length * 33, 'What the model knows: touch-move', 'Native unfold at depth two, without a selected case. It identifies the arbiter-judgment premise. The complete native tree is retained in touch-unfold.json.', [
  text(30, 40, 'WHAT THE MODEL KNOWS', 18, C.muted, 700),
  text(30, 75, "fide.laws.chess@0.1.1 · unfold('must_move_first_touched_piece', { depth: 2 })", 17, C.muted, 400, true),
  box(24, 94, 1052, 38, C.greenSoft), text(40, 120, 'question  must_move_first_touched_piece', 21, C.green, 650, true),
  ...visible.map((row, index) => text(36 + row.depth * 25, 161 + index * 33, row.role ?? '', 14,
    row.role === 'judgment' ? C.amber : C.muted, 600, true) + text(125 + row.depth * 25, 161 + index * 33,
    (row.prefix + row.name).slice(0, 70 - row.depth * 3), 17, row.producer ? '#5149a1' : C.ink,
    row.producer ? 650 : 400, true) + text(930, 161 + index * 33, row.anchor, 12, C.amber)),
  text(30, 157 + visible.length * 33, visible.length < rows.length - 1 ? `Excerpt: ${visible.length} of ${rows.length - 1} rows; complete tree in touch-unfold.json` : 'Native model view · no case selected · recursion depth is not formalization depth', 15, C.muted),
]));
const images = ['cover', 'model-to-answer', 'loss-and-exception', 'knows-touch'];
for (const name of images) execFileSync('rsvg-convert', [fileURLToPath(new URL(name + '.svg', assets)), '-o', fileURLToPath(new URL(name + '.png', assets))]);
const files = ['formalization-depth.json', 'touch-unfold.json', 'example-evidence.json',
  ...images.flatMap(name => [name + '.svg', name + '.png'])];
write('manifest.json', JSON.stringify({ format: 'arxo.fide-chess-readme-assets/1', worldHash: model.pin.worldHash,
  publicAssets: { repository: 'arxohq/arxo-fide-chess', tag: 'npm-v0.1.0' },
  tree: { predicate: 'must_move_first_touched_piece', depth: 2, lang: 'en', quote: 0, caseSelected: false },
  files: Object.fromEntries(files.map(name => { const bytes = readFileSync(new URL(name, assets));
    return [name, { bytes: bytes.length, sha256: 'sha256:' + createHash('sha256').update(bytes).digest('hex') }]; })),
}, null, 2) + '\n');
console.log('FIDE SVG/PNG figures generated from SDK evidence and native unfold.');
