# Reproduce and promote the autonomous FIDE OCI runtime

Use an exact public producer commit. Verify the original model inventory, profile/policies, runtime/build locks, host compatibility and tree pin. Online acquisition obtains exact host/builder/base artifacts; all later materialization, verification and build run offline without a core checkout.

```sh
python3 tools/acquire_mcp.py --root . --output /absolute/new-acquired
python3 tools/build_mcp.py --root . --acquired /absolute/new-acquired \
  --output /absolute/new-candidate --source-commit '<exact-public-SHA>' \
  --image 'arxo-fide-chess-mcp:preview-<exact-public-SHA>'
```

Two independent materializations must have the same tree and normalized archive. The accepted Linux host must match the runtime lock and complete real stdio/HTTP/source suite. Diagnostic or native-only receipts cannot promote an image. The actual final image is exercised with its enforced container policy; `candidate.json` binds the exact image archive, runtime archive, tree, host and execution receipts. Tree pins and receipts remain external to the hashed runtime. Docker registry manifest and config identities are distinct.

`mcp-verify.yml` has read-only publication permissions. The explicit `mcp-release.yml` promotion accepts only a successful main push run from that exact workflow, source SHA and external candidate SHA. It loads the already accepted OCI archive and publishes it without rebuilding. Its immutable GitHub preview release contains artifacts, pins and receipts. Existing tags/assets are never overwritten.

Before staging, independently verify anonymous registry pull by digest and release artifacts. GHCR visibility is separate from repository visibility. Ops consumes artifacts; it never builds the source on the deployment server.

The existing ops inventory selects `fide-chess` through `--instance fide-chess`; its projects/state/route are separate from CNAF. Require private HTTP stage acceptance, then public acceptance at the exact FIDE endpoint, actual first-activation rollback and reactivation. Every receipt is bound to the selected release and accepted cases/source policy. Other standalone services and legacy edge routes are invariants. Secrets stay in private server state.

Record readiness, first substantive request, RSS/peak RSS, actual request latency, timeout and 1/4/8-client measurements with conditions. These are addressed measurements, not an SLA. Full corpus stays not_checked; releaseVerified false.
