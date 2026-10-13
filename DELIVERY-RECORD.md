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
