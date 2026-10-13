# Reproduce and deliver the MCP npm wrapper

Use an exact committed public producer revision and its accepted `runtime.tar.gz`. `mcp/npm/host-pins.json` fixes runtime/archive/tree identity and the two already published shared platform hosts. The canonical portable helpers are explicitly exported from the corpus distribution layer; `mcp/helper-snapshot.json` pins their source bytes. No model compilation, relock or subject evaluator is part of npm assembly.

```sh
python3 tools/mcp_npm.py pack --root . \
  --runtime-archive /absolute/accepted/runtime.tar.gz \
  --binary linux-x64=/absolute/accepted/linux/law-mcp-server \
  --binary darwin-arm64=/absolute/accepted/mac/law-mcp-server \
  --host-archive linux-x64=/absolute/original-linux-host.tgz \
  --host-archive darwin-arm64=/absolute/original-mac-host.tgz \
  --source-commit '<exact-producer-SHA>' --out /absolute/new-npm-candidate
python3 tools/mcp_npm.py smoke /absolute/new-npm-candidate \
  --npx --receipt /absolute/new-installed-receipt.json
```

Use Python 3.12+ and Node.js 20+. Do not repack existing host archives: identical binaries with a rewritten README produce different immutable npm bytes. The wrapper uses exact optional dependency versions; it ships the accepted OCI data projection without `bin/law-mcp-server`. Its pin is bound into the launcher and every installed file is compared with the accepted archive.

Run native installed checks on Linux x64 and macOS arm64 at Node.js 20 and 24. The existing private `mcp-npm` channel admits only the trusted FIDE profile, public source commit and every acceptance/helper/template SHA before execution. It uses the established publisher; do not run npm publish from a workstation. Identical shared-host versions are skipped without retagging.

After publication independently verify version archive, package-root latest/README and ordinary anonymous `npx`. A transient npm CDN failure is a failed observation: retain it and retry verification, without republishing or bumping a version. Store durable immutable candidate archives and public-safe receipts. Full corpus remains not_checked; releaseVerified false.
