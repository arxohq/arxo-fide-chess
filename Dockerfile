# Context is the accepted runtime tree, not repository source or a host build.
ARG BASE_IMAGE=debian:bookworm-20251020-slim@sha256:3fc563f538cf97e350bb04f43ad234c5b100aa602cced60cd36d482336d45fd5
FROM ${BASE_IMAGE}
ARG SOURCE_COMMIT
ARG RUNTIME_TREE_DIGEST
LABEL org.opencontainers.image.title="Arxo fide-chess MCP technical preview" \
      org.opencontainers.image.source="https://github.com/arxohq/arxo-fide-chess" \
      org.opencontainers.image.revision="${SOURCE_COMMIT}" \
      org.arxo.runtime.tree.digest="${RUNTIME_TREE_DIGEST}"
COPY --chown=65532:65532 runtime/ /opt/arxo/runtime/
COPY --chmod=0555 mcp_entrypoint.sh /opt/arxo/mcp_entrypoint.sh
COPY NOTICE /opt/arxo/NOTICE
USER 65532:65532
WORKDIR /opt/arxo/runtime
EXPOSE 8722
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD ["/opt/arxo/mcp_entrypoint.sh", "healthcheck"]
ENTRYPOINT ["/opt/arxo/mcp_entrypoint.sh"]
CMD ["http"]
