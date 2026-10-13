![FIDE Laws of Chess on Arxo](https://github.com/arxohq/arxo-fide-chess/releases/download/npm-v0.1.0/cover.png)

# FIDE Laws of Chess on Arxo

**Explore a chess arbiter's decision through a pinned model, explicit facts and an inspectable answer.** Ten retained fictional cases cover illegal moves, flag fall, rapid/blitz exceptions, recording and arbiter judgment.

**Node.js 20+ · ESM · npm 0.1.0 · model 0.1.1 · FIDE edition effective 1 January 2023**

[Start in Node.js](#start-in-nodejs) · [Cases](#choose-a-case) · [Evidence](#inspect-the-evidence) · [Depth](#formalization-depth) · [Source repository](https://github.com/arxohq/arxo-fide-chess)

This is an independent open-source teaching and research demonstration. For an actual chess ruling, use the authentic FIDE Laws and the competent arbiter. Source text and model scope are pinned; the package does not claim general chess-engine capability or complete formalization.

## Start in Node.js

In a fresh directory:

```sh
npm init -y
npm install --ignore-scripts @arxo/canon-fide-chess@0.1.0 @arxo/law@0.4.3
```

Save this as `example.mjs`, then run `node example.mjs`:

```js
import { open } from '@arxo/law';
import { loadModel } from '@arxo/canon-fide-chess/chess';
import { game, white, getCaseInput } from '@arxo/canon-fide-chess/examples/arbiter';

const model = await loadModel();
const chess = await open(model.spec, {
  offline: true,
  local: { packages: { [model.spec]: model.package } },
});

const input = getCaseInput('SecondIllegal');
const loss = await chess.truth('game_lost_by', [game, white], input);
const draw = await chess.truth('game_drawn', [game], input);
console.log(loss.evaluationStatus, loss.truthStatus); // COMPUTED, TRUE_ONLY
console.log(draw.evaluationStatus, draw.truthStatus); // COMPUTED, NEITHER
```

Change the case to `SecondIllegalNoMate`: the draw is `COMPUTED / TRUE_ONLY`. Its input establishes that the opponent cannot checkmate by any legal series. The separate loss query is `REQUIRES_JUDGMENT / NEITHER` because other reachable loss grounds can still require arbiter judgments.

The SDK executes the rules through `@arxo/law-engine@0.5.3`. Installation alone does not register this distribution in the SDK's automatic canon resolver: keep the explicit `local.packages` handoff above. The loader implements no chess decisions or formulas.

![Model and episode to answer and proof](https://github.com/arxohq/arxo-fide-chess/releases/download/npm-v0.1.0/model-to-answer.png)

## Choose a case

| `getCaseInput(name)` | Episode | Checked question and result |
|---|---|---|
| `TouchIntentUnknown` | A movable own piece; intentional touch not adjudicated | `must_move_first_touched_piece`: `REQUIRES_JUDGMENT / NEITHER` |
| `FirstIllegal` | One completed illegal move | Loss: `REQUIRES_JUDGMENT / NEITHER`; draw: `COMPUTED / NEITHER` |
| `SecondIllegal` | Two illegal moves under the model's specified closure | Loss: `COMPUTED / TRUE_ONLY` |
| `SecondIllegalNoMate` | Two illegal moves; inability to checkmate established | Draw: `COMPUTED / TRUE_ONLY` |
| `FlagFall` | Flag observed, time control not completed, mate possible | Loss: `COMPUTED / TRUE_ONLY` |
| `FlagFallNoMate` | The same flag; inability to checkmate established | Draw: `COMPUTED / TRUE_ONLY` |
| `RapidFirstIllegal` | Rapid 15+10; first illegal move | Opponent receives 60 seconds; 120-second query is `NEITHER` |
| `BlitzFirstIllegalCompetitive` | Blitz 3+2 under competitive rules B.2 | Opponent receives 120 seconds; 60-second query is `NEITHER` |
| `ShortOfTimeRecording` | Standard chess, no increment, 240 seconds left | `must_record_moves`: `COMPUTED / FALSE_ONLY` |
| `DeviceWarning` | Electronic device evident; arbiter gave a warning | Loss and differing-penalty queries: `COMPUTED / TRUE_ONLY` |

All 18 original case/query expectations are retained and checked. The fixture export provides `caseNames`, `game`, `white`, `black`, `king`, `CaseName` and `getCaseInput(name)`. Each call returns an independent copy; an unknown name throws `RangeError`.

![Loss and the explicit inability-to-mate exception](https://github.com/arxohq/arxo-fide-chess/releases/download/npm-v0.1.0/loss-and-exception.png)

## Facts and arbiter judgments

`getCaseInput` preserves the CLI's canonical assertions, constants, context and options. The loader supplies neither absent facts nor adjudications. The model's explicitly declared closures are part of its rules; they are not a general assumption that a missing fact is false.

For touch-move, use the two declared arguments — player and piece:

```js
import { open } from '@arxo/law';
import { loadModel } from '@arxo/canon-fide-chess/chess';
import { white, king, getCaseInput } from '@arxo/canon-fide-chess/examples/arbiter';

const model = await loadModel();
const chess = await open(model.spec, {
  offline: true, local: { packages: { [model.spec]: model.package } },
});
const answer = await chess.truth(
  'must_move_first_touched_piece', [white, king], getCaseInput('TouchIntentUnknown'),
);
const document = JSON.parse(new TextDecoder().decode(answer.document));
console.log(answer.evaluationStatus, answer.truthStatus); // REQUIRES_JUDGMENT, NEITHER
console.log(document.results[0].judgmentRequests);
```

A positive, explicitly `adjudicated` intentional-touch assertion establishes this model's obligation; that path is checked separately. The original missing-judgment fixture stays unchanged.

Missing empirical facts, negative facts and contradictory support retain `NEITHER`, `FALSE_ONLY` and `BOTH`. For the checked empirical conflict, SDK 0.4.3 returns `COMPUTED / BOTH`: the query was computed and both polarities are supported. Read both fields; do not collapse them to a Boolean. Exact Decimal inputs, such as recorded points, are strings (`'0.75'`).

<details>
<summary>Complete canonical input for SecondIllegal</summary>

```json
{
  "legalTime": "2023-06-01",
  "assertions": [
    {
      "contentHash": "sha256:696ba690ec316ad1654c94c94886b3d6e9764573460a0ed89f76280496c904fa",
      "evidence": [],
      "id": "urn:law:examples:chess:arbiter#player",
      "kind": "assertion",
      "literal": {
        "args": [
          {
            "id": "urn:example:chess:game",
            "kind": "entity_ref"
          },
          {
            "id": "urn:example:chess:white",
            "kind": "entity_ref"
          }
        ],
        "kind": "literal",
        "polarity": "positive",
        "predicate": "urn:fide:laws:clir:chess#player_of"
      },
      "origin": "case_input",
      "package": "urn:law:examples:chess:arbiter"
    },
    {
      "contentHash": "sha256:9f7706ed8482cd04f869afdd849b90eea3c2e42ca246bf932c8a20f77a1fcc15",
      "evidence": [],
      "id": "urn:law:examples:chess:arbiter#complete-mate-facts",
      "kind": "assertion",
      "literal": {
        "args": [
          {
            "id": "urn:example:chess:white",
            "kind": "entity_ref"
          }
        ],
        "kind": "literal",
        "polarity": "positive",
        "predicate": "urn:fide:laws:clir:chess#checked_player"
      },
      "origin": "case_input",
      "package": "urn:law:examples:chess:arbiter"
    },
    {
      "contentHash": "sha256:cd688c83624c70688f10ead443e5c46c32ad7d3310696caf6dad9b80be7c1cb0",
      "evidence": [],
      "id": "urn:law:examples:chess:arbiter#illegal-count",
      "kind": "assertion",
      "literal": {
        "args": [
          {
            "id": "urn:example:chess:white",
            "kind": "entity_ref"
          },
          {
            "kind": "value",
            "type": {
              "name": "urn:law:std#Integer"
            },
            "value": 2
          }
        ],
        "kind": "literal",
        "polarity": "positive",
        "predicate": "urn:fide:laws:clir:chess#completed_illegal_move_count"
      },
      "origin": "case_input",
      "package": "urn:law:examples:chess:arbiter"
    }
  ],
  "context": {
    "decisionTime": "2026-09-08T12:00:00Z",
    "knowledgeTime": "2026-09-08T12:00:00Z",
    "legalTime": "2023-06-01",
    "timezone": "UTC"
  },
  "options": {}
}
```

This input was captured by released CLI 0.2.3 from the retained `.lawcase`; the fixture generator does not reproduce chess semantics. [Fixture bytes](https://github.com/arxohq/arxo-fide-chess/blob/main/npm/examples/arbiter-cases.json) · [Capture provenance](https://github.com/arxohq/arxo-fide-chess/blob/main/npm/examples/provenance.json).

</details>

## Inspect the evidence

Preserve `answer.document` as the canonical bytes returned by Arxo. Repeated executions of identical explicit inputs reproduce those bytes and their hashes. `answer.proof.nodes` identifies the applied rules and their premises.

The current SDK's `answer.sources` and proof-node source-anchor arrays are empty for these queries. Source links below are an explicit **static join** of executed producer IDs with anchors in the hash-checked model; they are not additional citations emitted by the evaluator. The pinned publication is the [FIDE Handbook, Laws 2023](https://handbook.fide.com/chapter/E012023).

This complete example saves the loss answer and prints its model anchor links:

```js
import { writeFile } from 'node:fs/promises';
import { open } from '@arxo/law';
import { loadModel } from '@arxo/canon-fide-chess/chess';
import { game, white, getCaseInput } from '@arxo/canon-fide-chess/examples/arbiter';

const model = await loadModel();
const chess = await open(model.spec, {
  offline: true, local: { packages: { [model.spec]: model.package } },
});
const answer = await chess.truth('game_lost_by', [game, white], getCaseInput('SecondIllegal'));
await writeFile('answer.json', answer.document);
const nodes = new Map(model.package.ir.nodes.map(node => [node.id, node]));
const sourceLinks = answer.proof.nodes.filter(node => node.rule).map(node => ({
  rule: node.rule,
  anchors: (nodes.get(node.rule)?.anchors ?? []).map(id => ({
    id, locator: nodes.get(id)?.locator,
  })),
}));
console.log(answer.hashes, sourceLinks); // includes SecondIllegalMoveLoses → article/7
```

<details>
<summary>What the model knows: native touch-move producer tree</summary>

![Native touch-move producer tree](https://github.com/arxohq/arxo-fide-chess/releases/download/npm-v0.1.0/knows-touch.png)

Produced by `chess.unfold('must_move_first_touched_piece', { depth: 2, lang: 'en', quote: 0 })`, with no selected case. [Complete native tree and text](https://github.com/arxohq/arxo-fide-chess/blob/main/npm/assets/touch-unfold.json). Recursion depth is separate from formalization depth.

</details>

## Model and loader API

| Import | Exact model spec | Exports |
|---|---|---|
| `@arxo/canon-fide-chess` | `fide.laws.chess@0.1.1` | `models`, `loadModel(exactSpec)`, error classes |
| `@arxo/canon-fide-chess/chess` | `fide.laws.chess@0.1.1` | `spec`, `loadModel()` |
| `@arxo/canon-fide-chess/examples/arbiter` | Retained case inputs | Identifiers, case names and independent input copies |

`loadModel` returns `{ spec, package, descriptor, pin, questionCatalog }`. Root imports read only the catalog and metadata. A load verifies original bytes before parsing the selected world and its catalog, then returns an independent model object. The descriptor remains separate: `package.meta.contentHash` is the linked world hash; `packageContentHash` is the original package hash. There are no model imports in this release.

Unknown or versionless specs fail with `ModelNotFoundError.code === 'MODEL_NOT_FOUND'`. Missing, corrupt or inconsistent model assets fail with `ModelIntegrityError.code === 'MODEL_INTEGRITY'`. There is no network fallback. TypeScript declarations cover exact specs, relation names, qualified relation names and fixture names; argument arity and value kinds are validated by the SDK at runtime.

## Formalization depth

| Model | Pinned edition | Measured unit / denominator | EXECUTABLE | Other measured levels | Status |
|---|---|---|---:|---|---|
| `fide.laws.chess@0.1.1` | Effective 1 January 2023 | `en_article` / 12 articles | 12 | INTERPRETED: 0, ANCHORED: 0, SOURCE_ONLY: 0, NONE: 0 | partial |

The existing `boundaries.depth` measure reads **own package nodes**, excluding imports, and the original article-division declaration. All 12 articles have deriving rules; this coarse measure does not establish complete formalization of every clause. 28 anchor references remain unresolved by this article measure and are recorded in the report.

The preface and Appendices A–D are outside this denominator. A and B have executable rules used by the rapid/blitz cases; C's notation and D's organizational material are not executed by this demonstration. Guidelines are outside the retained Laws publication. These areas remain unmeasured by the article report.

[Per-unit report](https://github.com/arxohq/arxo-fide-chess/blob/main/npm/assets/formalization-depth.json) records the denominator, edition, source/package/world hashes, original measurement implementation hashes and adapter hash. `EXECUTABLE`, source presence, completeness, declared scenarios and successful runs are separate claims. The model exposes institutional predicates and a procedure; it declares no deontic norms or full obligation-lifecycle positions.

## Scope and verification

The package evaluates presented episodes. Most board/history conditions remain explicit protocol facts. Its limited observed-position slice handles complete known four-piece K/Q/R frames and a specific inability-to-mate case; other positions remain outside that slice. It does not establish general position reachability, parse PGN or construct a tournament pairing. Rating, title, tie-break and Swiss-pairing models are separate packages and are not bundled.

Model 0.1.1 corrects four preparation defects while preserving the original expected outcomes: scoped procedure predicates in the fixtures, and an exact Decimal intermediate before half-point rounding. The selected package passes **103 source scenarios**, including six new numeric boundaries, through build, replay and rebuild. The installed demonstration checks all **18 retained questions**, loader failures/isolation, explicit and absent judgment, missing/negative/conflicting facts, score boundaries, canonical repeatability, README examples and strict TypeScript.

Checks are addressed to this distribution. Full corpus: `not_checked`; `releaseVerified: false`. Delivery checks do not establish subject accuracy or completeness.

## Source pins and reproduction

[Source pin](https://github.com/arxohq/arxo-fide-chess/blob/main/npm/source-pin.json) fixes original model/descriptor/world/catalog bytes and case inputs to an immutable public source revision. [Source origin](https://github.com/arxohq/arxo-fide-chess/blob/main/SOURCE-ORIGIN.json) separately records the corpus origins and addressed fixes. English source text is a pinned visible-text extraction (`PINNED_UNOFFICIAL_COPY`), not a claimed official PDF publication. FIDE attribution and publisher terms are retained in [NOTICE](https://github.com/arxohq/arxo-fide-chess/blob/main/NOTICE); Apache-2.0 covers Arxo-authored code and does not replace those terms.

To rebuild the wrapper from the pinned inputs in the repository:

```sh
git clone https://github.com/arxohq/arxo-fide-chess.git
cd arxo-fide-chess/npm
npm ci --ignore-scripts
npm run build -- --canon ..
npm test
npm run test:types
npm run candidate -- --out /absolute/new-candidate-directory
```

The candidate script prepares one local tarball and the existing `arxo.npm-candidate/1` manifest; it does not publish. Delivery uses the established CI in `arxo-io/law`. [Publishing and verification recipe](https://github.com/arxohq/arxo-fide-chess/blob/main/npm/PUBLISHING.md) · [Delivery record](https://github.com/arxohq/arxo-fide-chess/blob/main/DELIVERY-RECORD.md).
