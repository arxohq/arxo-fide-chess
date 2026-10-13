# Reproduce and deliver the FIDE demonstration

The wrapper is maintained only in this repository's `npm/`. Models and source cases are frozen independently of an ordinary npm build. Do not compile a live dirty corpus as an implicit packaging step.

1. Review the exact source pin and retained registry/case inputs. `node tools/build.mjs --canon ..` checks sizes, raw SHA-256 hashes, identity, semantics, descriptors and catalogs before generating entries and TypeScript declarations.
2. Run the addressed loader/runtime and strict type checks. `getCaseInput` preserves canonical CLI assertions, constants, context and options. New captures use the explicitly selected released CLI, with model changes admitted and frozen before packaging.
3. Generate SVG/PNG figures from SDK answers and native unfold with `node tools/readme-assets.mjs`; visually inspect them. Depth uses the original `boundaries.depth` implementation and records per-unit evidence, original implementation hashes and unmeasured areas. It is not a rule-count percentage.
4. Prepare exactly one candidate outside Git: `npm run candidate -- --out /absolute/new-directory`. Preserve the resulting tarball, inventory and `facade-npm.json` with schema `arxo.npm-candidate/1`.
5. Install that exact tarball in fresh Node.js 20 and 24 consumers together with `@arxo/law@0.4.3` and TypeScript 5.9.3. Run all README JavaScript blocks, retained runtime checks, the bundled example and strict type fixture with ES2022, DOM and ESNext.Disposable; do not use skipLibCheck.
6. Check archive inventory, licences/notices, hashes, absence of authoring caches and machine paths. Upload the immutable PNGs and archive as appropriate to the authorized repository/release; anonymously verify asset bytes before npm delivery.
7. Use `apps/delivery/candidate.py upload` and `.github/workflows/publish-facade-npm.yml` in the infrastructure repository **arxo-io/law**. Register only this package in its owned candidate and channel entry; preserve other candidates. Use a new isolated sparse delivery checkout. A `facade-npm/<name>` branch is a dry run; `facade-npm/publish-<name>` performs the authorized publication.
8. Verify CI, npm version/latest, tarball SHA and bytes, anonymous ordinary installation, README, types and public assets. Do not probe an unpublished version endpoint or republish because of metadata propagation delay.

Publish through CI only, never from a local workstation. No SDK or unchanged canon is republished for this wrapper. Keep `releaseVerified: false` and the full corpus `not_checked`; addressed delivery checks and subject acceptance are separate.

The corpus runtime lock used during preparation was unpublished. The explicit public CLI 0.2.3 override is classified UNPINNED relative to that corpus lock and separately identified by version and binary hash. Reproduction has no Cargo or in-process subject-evaluation fallback.

Captured FIDE text retains publisher terms and attribution in NOTICE. The Arxo code licence does not grant rights in the publisher text or FIDE endorsement. Source changes require a new model snapshot and corresponding pin; a changed published npm archive requires a new npm version.
