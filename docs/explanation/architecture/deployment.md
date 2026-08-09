# Deployment and operations

## Runtime deployment

The reconstructor is a local CLI. Large ELF inputs, expanded dumps, SQLite sidecars, generated
headers, and logs remain outside source control. A persistent source-bound index is encouraged for
the large PS4 compressed dump; routine cleanup must preserve it.

The standard non-proprietary external-tool baseline is
`tools/binary_toolchain/compose.yaml`. Inputs are mounted read-only and outputs are published
outside the repository. Sony SDKs, SELF credentials, and proprietary binaries are never copied
into the container.

## Linux compatibility and profiling deployment

`ops/reconstructor/compose.yaml` is a separate developer-only image for Linux compatibility checks
and opt-in performance evidence. It uses pinned CPython 3.14.7 and uv 0.12.3 dependencies, mounts the
checkout read-only at `/workspace`, and publishes application logs, generated output, source-bound
caches, raw profiler files, and an external history database through explicit host mounts. The
image does not contain ELF files, compressed DWARF dumps, Doris, Sony SDKs, credentials, or generated
artifacts.

The default service has no extra host privileges. The `py-spy` Compose profile adds only
`SYS_PTRACE`; `pid: host` and unrestricted seccomp are not part of the normal contract. If a local
Docker runtime requires further process-inspection permission, that is a separately labelled
environmental blocker rather than a reason to grant the normal service broader access.

The container connects to the existing Doris Compose project through `host.docker.internal` when
the analytical store workflow needs the serving backend. Doris load, tablet, statistics, and query
profile evidence remains owned by the analytical service and is not inferred from Python profiler
output.

## Doris serving-variant boundary

The canonical serving path is an immutable source-bound fourteen-family `DUPLICATE KEY`
publication. Optimization experiments run beside it as external, source-bound candidates. Each
candidate carries a variant ID plus source, schema, DDL, configuration, statistics, index,
storage, compression, and load identities; candidate DDL and population are isolated from the
canonical registry and require an explicit optimization command. The generation executor can
write redacted query observations and bounded FE-local profiles to an external JSONL artifact, but
tracing is disabled by default and incomplete profile retrieval is `partial` evidence. A candidate
is not promoted from an improved `EXPLAIN`: exact row/order/header hashes, terminal statistics,
healthy tablets, and representative cold/warm end-to-end latency must pass the existing acceptance
gate.

The first complete-corpus evaluation on 2026-08-09 kept the canonical physical variant and found
that sequential DIE/attribute/reference/unit hydration, rather than Doris scan CPU, dominated the
generation path. The serving runtime now uses bounded source/unit-aware batches. Exact exhaustive
`rAIFSM` runs completed in `32.123 s` fresh and `31.683 s`/`31.653 s` repeated, versus the earlier
`361.004 s` warm process sample; all 11 headers matched. A paired traced run also matched all
headers, but tracing added `160.1%` wall time and its FE profiles were `partial`, so it is
attribution evidence only. The source/name candidate was exact but did not improve warm lookup
latency. The canonical schema, keys, buckets, storage, indexes, and registry remain unchanged.

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
| unmeasured Doris fan-out or query attribution | source-bound lookup candidates and opt-in generation query traces | external optimization report |
| incomplete or conflicting DIE evidence | typed status/provenance and authority rules | deterministic tests |
| generated header closure failures | exact manifests plus optional MSVC/Sonar evidence | local acceptance only |
| documentation drift | strict Zensical build in `just check` and source-backed pages | docs CI build |
| graph semantics overclaiming | JSONL projection documented as current; live ingestion on roadmap | knowledge bundle manifest |
