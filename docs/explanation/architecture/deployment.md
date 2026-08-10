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

The first complete-corpus evaluation on 2026-08-09/10 kept the canonical physical variant and found
that sequential DIE/attribute/reference/unit hydration, rather than Doris scan CPU, dominated the
generation path. The serving runtime now uses bounded source/unit-aware batches, child-frontier and
reference prefetching, per-unit line-program caching, and semantic operation tracing when explicitly
enabled. The post-policy canonical eager/full/all run measured `19.121/19.127 s` warm p50/p95; all
11 headers matched. Lazy reference prefetch reduced trace query count from 754 to 680 but cleared
only 5.3% of paired warm latency, while the decoded attribute projection reduced warm p95 RSS by
15.1% without clearing the latency gate. Both remain opt-in. A targeted child-tag predicate was
exact but regressed warm p50 by 10.5% and was rejected. Name lookup candidates reduced global
lookup tablet scheduling but did not clear the confirmatory p95 gate. A grouped-count rewrite was
exact but end-to-end tied with the raw path and was removed. The canonical schema, keys, buckets,
storage, indexes, and table data remain unchanged; the source registry only gained the additive
serving-variant identity fields.

The fair-path `unit-bound-hydration` screen preserved exact output but took `289.048 s` for
exhaustive `rAIFSM` versus the canonical `19.121/19.127 s` warm p50/p95. Its partial trace
expanded attribute/reference/child-tag operations to `9,262/7,579/9,136` queries from
`85/154/25`; the candidate is rejected because unit predicates increased scheduling fan-out.

The subsequent `combined-positive-below-gate` interaction test activated every candidate that had
shown roughly 5% or better standalone improvement: lazy reference prefetch, decoded-serving
attribute projection, and name lookup buckets 2/4/8, with b8 active. It preserved the exact
approved 11-file output and improved confirmatory warm `rAIFSM` p50/p95 from `19.1208/19.1271 s`
to `16.1152/16.1187 s` (`15.7%` at both quantiles); warm p95 RSS also fell by about 17%. The
active auxiliary table adds `7.23%` to canonical storage. A follow-up selective analysis produced
two manual `FINISHED` jobs with zero failed subjobs, clearing the current statistics gate. It
remains an opt-in variant because the decoded-serving projection is not lossless for raw
attribute values outside the proven generation path; the canonical fourteen-family deployment is
still the default.

The optimization command is a reusable, change-triggered evidence tool rather than a continuously
running service. It is rerun when the generator, source publication, Doris image/configuration,
candidate variant, or representative workload changes.

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
