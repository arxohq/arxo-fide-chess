# Arxo FIDE chess consumer kit

Keep documentation in English. Preserve unrelated dirty files. Never stash,
reset, restore or clean another contributor's work.

Model sources are under `packages/fide.laws.chess`; frozen model assets and
their descriptors are under `registry/`. The Node.js wrapper is maintained
only under `npm/`. It validates and loads pinned bytes; all chess decisions
and arithmetic belong to the model and the Arxo engine.

For wrapper changes run `npm ci --ignore-scripts`, `npm run build`, `npm test`
and `npm run test:types` from `npm/`. Verify a new tarball in a fresh consumer
on the minimum supported Node version. For source changes use the explicitly
pinned released CLI, check only this package and regenerate the frozen inputs
before changing the source pin. Do not change scenario expectations to fit an
implementation. Do not run a full subject corpus or general core gates here.

Publication uses the existing `arxo-io/law` candidate delivery workflow;
never publish npm from a local workstation. External publication requires
the owner's instruction. Keep `releaseVerified: false` and the full corpus
`not_checked` for addressed demonstration releases.
