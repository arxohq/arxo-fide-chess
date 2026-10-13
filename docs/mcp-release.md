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

## Accepted delivery — 14 October 2026

Both channels are publicly accepted: `npx -y @arxo/mcp-fide-chess@0.1.0` and [HTTPS MCP](https://mcp.arxo.io/mcp/fide-chess), with [health](https://mcp.arxo.io/healthz/fide-chess). The backend requires its private Bearer; the public edge accepts anonymous clients and refuses a foreign Origin.

| Identity | Frozen value |
|---|---|
| Model | `fide.laws.chess@0.1.1` |
| Model source | `3550570cef14da097ae92250f8e1b953f8a040e6` |
| OCI producer | `03df2df0e13b8107f6f46a5dd49ba91d75a95e58` |
| npm consumer/tools | `07814ec6e7fffcef56138018187e52e6f7ee1670` |
| Runtime tree | `sha256:f24f215b5e63c2fa2470a219386786ddf494805b04b3afd549c156633b73ea04` |
| Runtime archive | `sha256:8f1a805a60ea81bfa965de72f54f8d130e95cfa957e29894a3b7f25a0b4f870b` |
| OCI registry manifest | `sha256:8b5e5bf32791835d864d2065170698fdd6ecd00330d615dab8fb5c45ed9e4a16` |
| OCI config | `sha256:4102fd0be7928891ffe96015f33432873322a9975224a4daac67452fdccd5c05` |
| npm wrapper archive | `sha256:dd0283b730587b3b122c77025f9d4f9ecb67cc2832b3ddfbd426833b9f14c0ed`, 146,657 bytes |

[Immutable OCI artifacts and receipts](https://github.com/arxohq/arxo-fide-chess/releases/tag/preview-03df2df0e13b8107f6f46a5dd49ba91d75a95e58) and [accepted npm candidate](https://github.com/arxohq/arxo-fide-chess/releases/tag/mcp-npm-candidate-0.1.0-07814ec6e7fffcef56138018187e52e6f7ee1670) retain exact accepted bytes. [OCI verification](https://github.com/arxohq/arxo-fide-chess/actions/runs/38467341778) accepted 119 runtime and 61 actual-image checks; [promotion](https://github.com/arxohq/arxo-fide-chess/actions/runs/38467644500) reused that image. Two independent materializations and the CI archive matched every raw runtime file/mode/hash. The original 87 model inputs and 103 scenarios remain unchanged; ten published examples retain all 18 original expectations. The MCP suite adds explicit judgment/support/Decimal/denial cases without rerunning the full corpus.

Clean macOS arm64 Node 20.20.2/24.21.0 and Linux x64 Node 20/24 consumers passed anonymous installation and literal cold npx, 58 actual MCP/source checks per content run, complete installed-file comparison, JSON-RPC-only stdout, EOF and outer-client SIGTERM with stdin kept open. Linux consumer matrix uses Docker/Rosetta; native Linux Node 20 is separately accepted by the publisher CI. npm 11 cache-lock failures on the macOS bind filesystem were retained and resolved by using a fresh Linux filesystem; no archive/version/source republishing was used. Shared-host archives and their tags are unchanged.

On the Arxo server, private staging and the final public endpoint each passed the full 61 HTTP checks. First activation was actually rolled back: its routes returned 404, its projects/networks were absent, and the same accepted artifact was then reactivated. CNAF and legacy container IDs/start times, accepted pins, state/config/secret metadata and previously healthy routes were identical throughout. Final public receipt SHA `0105167dd9678e425b8cc73a9c666516ac3a4c44809524e46ee8ba6f24a73bed`; first-rollback receipt SHA `d468cb7c89c8099032bccb8d5d736ad856bb594efe9b9f7f9298a08453706796`.

[Final delivery receipt](https://github.com/arxohq/arxo-fide-chess/releases/download/mcp-npm-candidate-0.1.0-07814ec6e7fffcef56138018187e52e6f7ee1670/delivery-receipt.json) has SHA-256 `03b1623b7102ffc63059d3c477ac389032b7220710f44a6345fa0efc6efd7f6f`. The same immutable release contains public acceptance summaries for [Linux](https://github.com/arxohq/arxo-fide-chess/releases/download/mcp-npm-candidate-0.1.0-07814ec6e7fffcef56138018187e52e6f7ee1670/linux-public-acceptance.json), [macOS](https://github.com/arxohq/arxo-fide-chess/releases/download/mcp-npm-candidate-0.1.0-07814ec6e7fffcef56138018187e52e6f7ee1670/macos-public-acceptance.json) and the [deployed server](https://github.com/arxohq/arxo-fide-chess/releases/download/mcp-npm-candidate-0.1.0-07814ec6e7fffcef56138018187e52e6f7ee1670/server-acceptance.json), with separate checksum files. These reports preserve receipt identities without internal machine paths or secrets.

### Addressed server measurements

The backend remains limited to 1 CPU, 512 MiB and 128 PID. Images and OS caches were retained; these are not cold-install or SLA measurements. First public backend creation to health was 622.100 ms and the first fresh substantive request was 470.161 ms. Same-artifact reactivation was 773.161 ms; an own-service restart was 544.875 ms. Final process RSS was 76,720 KiB and VmHWM was 115,628 KiB; an earlier observed public peak was 195,424 KiB.

| Concurrent clients | Pinned reference requests | Median latency | Maximum latency | Timeouts/failures |
|---|---:|---:|---:|---:|
|1|3|30.414 ms|59.283 ms|0|
|4|12|281.661 ms|1291.756 ms|0|
|8|24|1100.486 ms|5531.993 ms|0|

A separate heavier parallel execution probe returned `CALL_TIMEOUT` at the configured 30-second limit while the process stayed healthy. That failed probe is retained; its exact elapsed/concurrency phase was not captured and is not reconstructed. The stage was cleanly restarted before the successful full serial acceptance. A response timeout does not imply cancellation of synchronous calculation. The measurements establish the stated cheap-request boundary, not general execution capacity.

Technical preview remains `fullCorpus: not_checked`, `releaseVerified: false`.
