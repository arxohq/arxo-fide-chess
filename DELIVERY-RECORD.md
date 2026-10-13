# FIDE Laws of Chess consumer distribution

The owner requested a public repository and demonstrational Node.js npm
package, and asked for defects found during preparation to be fixed.

Audience: developers, chess arbiters and readers exploring rules as executable
models. Destinations: `arxohq/arxo-fide-chess` and
`@arxo/canon-fide-chess@0.1.0`. Node.js 20+, ESM; explicit
`@arxo/law@0.4.3` with published engine `@arxo/law-engine@0.5.3`;
strict TypeScript 5.9.3 without `skipLibCheck`.

The source model is `fide.laws.chess@0.1.1`, semantics `law.core/0.2.11`,
with no model imports. It retains the FIDE edition effective 1 January 2023,
the original source anchors and original question catalog. The original
corpus revision is `30b247f6e9aae8eb08ca6057b413c9f0133945d3`; the addressed
fix revision is `8fd03509d66c12d4eaf55fdae7d13fbea4a64e56`.

The original 0.1.0 model had four failures out of 97 scenarios on released
CLI 0.2.2 and 0.2.3. The failures were addressed without changing expected
outcomes: procedure fixtures now use their actual scoped `GamePlay__…`
predicates, and a typed Decimal half-point relation preserves the existing
score criterion at `round`'s input. Six numeric boundary scenarios were added.
The fixed package passes all 103 scenarios through the existing `package.py`
build, replay and rebuild path with released CLI 0.2.3.

The standalone corpus runtime lock is unpublished. Source preparation uses
an explicit `LAW_BIN` override, classified `UNPINNED` relative to that lock;
the selected public CLI version and binary hash are captured separately.
There is no Cargo fallback or new subject evaluator in the preparation tools.

Ten original arbiter cases and their 18 original case/query expectations
form the installed-package demonstration. Their canonical inputs are captured
by the released CLI, including context, constants and options. The publisher
text and Arxo code licences remain separate in NOTICE. A code licence does
not replace publisher terms or claim FIDE endorsement.

Depth is measured by the existing `boundaries.depth` over own package nodes.
The denominator, source/model and implementation hashes, edition and
unmeasured areas are retained in the per-unit report. Executable article
coverage is separate from completeness and successful scenario execution.

Publication and installed-consumer results are recorded after verification.
Full corpus: `not_checked`; `releaseVerified: false`.

## Prepared and locally verified

The exact 524,353-byte tarball has SHA-256
`0d81c3be34783400ac1f35774fbc13ea22285b2412cb8159c9c2914cedecc9d1`.
Fresh installed consumers on Node.js 20.20.2 and 24.21.0 passed nine runtime
groups, all 18 retained case/query expectations, strict TypeScript 5.9.3,
all three JavaScript blocks in each GitHub/npm README and the bundled example.
Archive inventory, original asset hashes, licences/notices and absence of
private authoring caches and machine paths were checked. Four SVG/PNG figures
were generated from SDK evidence and native unfold and visually inspected.

The original code-fix revision is recorded above; the corpus question-catalog
follow-up is `6225feb5cc3960bc251426b45b83e065456ba5be`. The public immutable
source pin is `3550570cef14da097ae92250f8e1b953f8a040e6`.
The intermediate score producer is classified as internal in the retained
question catalog. Source anchors are a static join from executed producer
IDs to the pinned model; the current SDK source-anchor arrays are empty.

These local checks do not assert public publication or full subject acceptance.
See `verification/delivery-checks.json` for the prepared evidence.

## Public delivery

The repository is public. [Public CI](https://github.com/arxohq/arxo-fide-chess/actions/runs/38452471203) passed on Node.js 20 and 24 and reproduced the pinned CLIR on Linux. The released CLI install/ask commands passed in a fresh public clone.

[Dry run](https://github.com/arxo-io/law/actions/runs/38452941907) and [npm publication](https://github.com/arxo-io/law/actions/runs/38453113544) succeeded. npm 0.1.0 is published under latest. The version endpoint and public archive were verified anonymously against the exact prepared SHA-256 and size. [README assets](https://github.com/arxohq/arxo-fide-chess/releases/tag/npm-v0.1.0) are public; all four PNGs were downloaded anonymously and match the shipped manifest.

Root npm metadata propagation and ordinary installation are checked separately. The first ordinary install encountered an npm CDN 404 after the version endpoint was already available; it is preserved as a failed propagation attempt, not a reason for another publication. Full corpus: `not_checked`; `releaseVerified: false`.
