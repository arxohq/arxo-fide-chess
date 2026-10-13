#!/bin/sh
# Only deployment credentials and bounded-call settings reach the host.
set -eu
mode=${1:-http}
[ "$#" -le 1 ] || { echo 'Only http, stdio or healthcheck are accepted' >&2; exit 64; }
case "$mode" in
  http|stdio|healthcheck) ;;
  *) echo 'Only http, stdio or healthcheck are accepted' >&2; exit 64 ;;
esac
port=${FIDE_CHESS_MCP_PORT:-8722}
case "$port" in ''|*[!0-9]*) echo 'Invalid FIDE_CHESS_MCP_PORT' >&2; exit 64 ;; esac
[ "$port" -gt 0 ] && [ "$port" -le 65535 ] || exit 64
timeout=${FIDE_CHESS_MCP_CALL_TIMEOUT:-30}
case "$timeout" in ''|*[!0-9]*) echo 'Invalid FIDE_CHESS_MCP_CALL_TIMEOUT' >&2; exit 64 ;; esac
[ "$timeout" -gt 0 ] && [ "$timeout" -le 110 ] || exit 64
if [ "$mode" = http ] && [ -z "${FIDE_CHESS_MCP_TOKEN:-}" ]; then
  echo 'FIDE_CHESS_MCP_TOKEN is required for HTTP' >&2; exit 64
fi
set -- /opt/arxo/runtime/bin/law-mcp-server --root /opt/arxo/runtime --profile fide-chess
case "$mode" in
  http) set -- "$@" --http --host 0.0.0.0 --port "$port" ;;
  healthcheck) set -- /opt/arxo/runtime/bin/law-mcp-server --healthcheck --port "$port" ;;
esac
exec /usr/bin/env -i PATH=/usr/bin:/bin HOME=/state LANG=C.UTF-8 \
  LAW_MCP_TOKEN="${FIDE_CHESS_MCP_TOKEN:-}" \
  LAW_MCP_ALLOWED_ORIGINS="${FIDE_CHESS_MCP_ALLOWED_ORIGINS:-}" \
  LAW_MCP_CALL_TIMEOUT="$timeout" LAW_MCP_LOG=0 \
  LAW_MCP_ARTIFACT_DIR=/state/artifacts "$@"
