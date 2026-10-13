# Ten retained chess-arbiter cases

These fictional cases retain their original facts, dates and 18 expected case/query outcomes. Their lock pins `fide.laws.chess@0.1.1`; the npm distribution provides canonical CLI-captured inputs as `getCaseInput`.

See [the Node.js guide](../../npm/README.md#choose-a-case) for the complete case matrix, explicit judgment handling and source/proof inspection.

From the repository root, use the released CLI explicitly:

```sh
npm exec --yes --package=@arxo/cli@0.2.3 -- law install --project examples/arbiter --registry arxo=registry
npm exec --yes --package=@arxo/cli@0.2.3 -- law ask examples/arbiter --case SecondIllegal --query-json examples/arbiter/queries/loss.json --out "$(mktemp -d)"
```

The first command restores pinned dependency bytes; it does not choose a model version. `SecondIllegalNoMate` establishes a draw. `TouchIntentUnknown` requires an arbiter's intentional-touch judgment. Preserve full evaluation statuses and canonical output; see `expectations.json` for every saved question.
