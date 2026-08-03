# Deployment and operations

## Runtime deployment

The reconstructor is a local CLI. Large ELF inputs, expanded dumps, SQLite sidecars, generated
headers, and logs remain outside source control. A persistent source-bound index is encouraged for
the large PS4 compressed dump; routine cleanup must preserve it.

The standard non-proprietary external-tool baseline is
`tools/binary_toolchain/compose.yaml`. Inputs are mounted read-only and outputs are published
outside the repository. Sony SDKs, SELF credentials, and proprietary binaries are never copied
into the container.

## Documentation deployment

Zensical builds the checked-in `docs/` tree into `site/`. The repository's Pages workflow installs
the locked Node documentation validators, runs the local `uv run just docs-check` contract, uploads
`site`, and deploys it through GitHub Pages. The workflow pins every external action to a full
commit SHA and uses both `uv.lock` and `tools/documentation/package-lock.json` as dependency
contracts.

Developer-only observability and quality tooling is deliberately separate from this runtime
deployment. [Langfuse](../../how-to/observability/langfuse.md) runs as a loopback Docker stack for
Copilot/Codex traces; [SonarQube](../../how-to/quality/sonarqube.md) consumes a local MSVC
compilation database for generated headers. Neither is required to run the offline reconstructor,
and neither is a substitute for deterministic producer or repository acceptance evidence.

## Quality risks

| Risk | Mitigation | Evidence boundary |
| --- | --- | --- |
| 30+ GB expanded dump | streaming parser and persistent SQLite index | explicit real-asset run |
| stale source-bound cache | identity catalog, fingerprints, atomic publication | artifact manifests |
| incomplete or conflicting DIE evidence | typed status/provenance and authority rules | deterministic tests |
| generated header closure failures | exact manifests plus optional MSVC/Sonar evidence | local acceptance only |
| documentation drift | strict Zensical build in `just check` and source-backed pages | docs CI build |
| graph semantics overclaiming | JSONL projection documented as current; live ingestion on roadmap | knowledge bundle manifest |
