# FIDE Laws of Chess MCP on Arxo

Run a pinned FIDE Laws of Chess model as a local MCP server:

```sh
npx -y @arxo/mcp-fide-chess@0.1.0
```

Node.js 20+, Linux x64 or macOS arm64. The command waits for MCP JSON-RPC messages on standard input; it is not an interactive chess program. Installation uses npm; execution uses the packaged model and exact shared native host locally.

## MCP client configuration

```json
{
  "mcpServers": {
    "arxo-fide-chess": {
      "command": "npx",
      "args": ["-y", "@arxo/mcp-fide-chess@0.1.0"]
    }
  }
}
```

The distribution pins `fide.laws.chess@0.1.1`, its resources and the FIDE edition effective 1 January 2023. It exposes reference and execution tools. Supply game circumstances as facts, with explicit `legalTime` and a context containing `timezone`, `decisionTime` and `knowledgeTime`. Missing arbiter judgments remain missing; the server does not simulate a board or decide intent. Read `evaluationStatus` and `truthStatus` separately and inspect the actual proof and judgment requests.

The package checks the complete data inventory, pin and selected platform binary before startup. Each process has private temporary state, removed on EOF or termination. `FIDE_CHESS_MCP_CALL_TIMEOUT` accepts an integer from 1 to 110 seconds (default 30). Native execution does not provide the Docker network or resource limits. Do not omit optional dependencies.

The HTTP service is deployed separately at `https://mcp.arxo.io/mcp/fide-chess`; its accepted deployment identity and status are recorded in the public repository.

[Usage, inputs and limitations](https://github.com/arxohq/arxo-fide-chess/blob/main/docs/mcp.md) · [Reproduction and delivery](https://github.com/arxohq/arxo-fide-chess/blob/main/docs/mcp-npm-release.md)

Technical preview: full corpus `not_checked`; `releaseVerified: false`. Arxo code licensing and FIDE publisher text terms are separate; see NOTICE. This independent distribution does not claim FIDE endorsement or general chess-engine capability.
