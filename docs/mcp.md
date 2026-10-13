# FIDE Laws of Chess MCP

The standalone MCP serves exactly `fide.laws.chess@0.1.1` and its pinned resources, based on the FIDE edition effective 1 January 2023. Reference and execution tools run on the shared native Arxo host. The interface and rule prose are English; original model metadata are retained unchanged.

## Local stdio

```sh
npx -y @arxo/mcp-fide-chess@0.1.0
```

Node.js 20+, Linux x64 and macOS arm64. The command waits for JSON-RPC on stdin. Use this MCP client configuration:

```json
{ "mcpServers": { "arxo-fide-chess": { "command": "npx", "args": ["-y", "@arxo/mcp-fide-chess@0.1.0"] } } }
```

Installation acquires npm archives; execution reads only the pinned local runtime. Optional platform dependencies are required. The launcher verifies all data and host bytes before startup and creates private temporary state. EOF and termination remove it. `FIDE_CHESS_MCP_CALL_TIMEOUT` accepts integer seconds from 1 to 110, default 30. Native execution does not promise Docker's network or memory sandbox.

## HTTP and container

The separately deployed public service uses `https://mcp.arxo.io/mcp/fide-chess`; health is `https://mcp.arxo.io/healthz/fide-chess`. Its backend is private and Bearer protected. The edge supplies its server-side token; clients need no token. Origin checks remain active. Exact deployment identity and acceptance state belong to the delivery record, not a mutable image tag.

For a local container, use the accepted registry digest from the immutable release and `compose.yaml`. Runtime data and binary are read-only. The backend has no outgoing runtime network access; limits are 1 CPU, 512 MiB, 128 PID and bounded temporary state/logs. The native response timeout does not promise cancellation of a synchronous calculation.

## Inputs and results

The root runtime key is `fide-laws-chess`. Discover declarations with `law_packages`, `law_search` and reference tools, then ask with `law_ask`. Every execution supplies `legalTime` and `context` with `timezone`, `decisionTime` and `knowledgeTime`. [Complete accepted requests](../mcp/cases/acceptance.json) retain the original ten examples and 18 expectations plus explicit missing/adjudicated judgments, negative/conflicting facts, Decimal boundaries and surface refusals.

Facts retain declared argument order, exact typed values, polarity and provenance. Missing empirical evidence is not false. Intent and other arbiter judgments are not supplied automatically. Read both `evaluationStatus` and `truthStatus`; inspect producer proofs, judgment requests and actual runtime source fragments. The retained static rule-to-source join is labelled separately from emitted runtime citations.

No board simulation or move search is provided. Rating, titles, tie-breaks and Swiss Dutch are not in this release. Editing, external publication, process simulation and unaccepted facets are unavailable. The question catalog is metadata; its presence does not register cases or expand the accepted API.

## Pins and evidence

[Model source pin](../npm/source-pin.json) fixes original source/model assets. [MCP delivery contract](../mcp/delivery.json), runtime/build locks, policies and tree pin describe this separate delivery. The same binary-free dataset is carried by npm and OCI. Each supported host binary is pinned by SHA; model version, producer commit, runtime tree, archive SHA and OCI manifest/config identities are separate.

[OCI reproduction](mcp-release.md) · [npm reproduction](mcp-npm-release.md)

This is an independent technical preview. Arxo code licensing does not replace FIDE publisher-text terms; see NOTICE. Full corpus `not_checked`; `releaseVerified: false`. Native and delivery acceptance does not establish completeness or official FIDE endorsement.
