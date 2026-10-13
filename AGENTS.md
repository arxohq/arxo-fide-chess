# Arxo FIDE chess consumer kit

Keep documentation in English. Preserve unrelated dirty files. Never stash,
reset, restore or clean another contributor's work.

Model sources are under `packages/fide.laws.chess`; frozen model assets and
their descriptors are under `registry/`. The model-library Node.js wrapper is maintained
only under `npm/`. The separate native MCP npm wrapper is under `mcp/npm/`.
Both validate and load pinned bytes; all chess decisions
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

For standalone MCP changes use the public `tools/` delivery entrypoints and
the hash-pinned shared helper snapshot. Run addressed Python/launcher guards
and real MCP cases; keep the original models, locks and fixture inputs intact.
Acquire exact dependencies before offline verification; do not import a
core/authoring checkout or rebuild the shared host. The existing npm and OCI
channels publish only accepted immutable artifacts. OCI deployment is an
independent FIDE instance selected from the ops inventory.
