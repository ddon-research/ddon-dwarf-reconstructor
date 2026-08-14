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
publication plus the source/name b8 lookup table. The canonical loader creates and refreshes that
auxiliary table from the source-bound index; it does not change the fourteen-family row contract or
registry counts. Optimization experiments remain beside it as external, source-bound candidates.
Each candidate carries a variant ID plus source, schema, DDL, configuration, statistics, index,
storage, compression, and load identities; candidate DDL and population are isolated from the
canonical registry and require an explicit optimization command. The generation executor can
write redacted query observations and bounded FE-local profiles to an external JSONL artifact, but
tracing is disabled by default and incomplete profile retrieval is `partial` evidence. A candidate
is not promoted from an improved `EXPLAIN`: exact row/order/header hashes, terminal statistics,
healthy tablets, and representative cold/warm end-to-end latency must pass the existing acceptance
gate.

The first complete-corpus evaluation on 2026-08-09/10 kept the canonical physical family design and found
that sequential DIE/attribute/reference/unit hydration, rather than Doris scan CPU, dominated the
generation path. The promoted serving runtime now uses bounded source/unit-aware batches, lazy
reference prefetch, the decoded-serving attribute projection, the b8 source/name lookup,
child-frontier prefetching, per-unit line-program caching, and semantic operation tracing when
explicitly enabled. The prior canonical eager/full/all run measured `19.121/19.127 s` warm p50/p95;
the promoted combined path measured `16.1152/16.1187 s`, and all confirmed outputs matched. Raw
attribute columns remain in the canonical attribute family; only the generation fetch projection is
narrowed. The full Season 2 run then validated that projection across all 289 requested roots. A
targeted child-tag predicate was exact but regressed warm p50 by 10.5% and was rejected.
b2 and b4 name lookup tables, grouped-count rewrites, and the remaining physical matrix stay
comparison-only or unobserved. The canonical keys, buckets, storage, indexes, and fourteen-family
registry contract remain unchanged; the source registry carries additive serving-variant identity
fields.

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
two manual `FINISHED` jobs with zero failed subjobs, clearing the current statistics gate. This
interaction is now the canonical generation serving path; raw attribute values remain available in
Doris for evidence consumers, while generation uses the bounded serving projection. The b8 table is
the default lookup table; b2 and b4 are comparison-only alternatives.

The optimization command is a reusable, change-triggered evidence tool rather than a continuously
running service. It is rerun when the generator, source publication, Doris image/configuration,
candidate variant, or representative workload changes.

The complete Season 2 header closure is independently validated outside the runtime path. The
final external input contains 289 bundles and 2,760 headers; MSVC `14.51.36231` compiled every
header as a separate translation unit with zero failures or timeouts. The audit corrected nested
base dependency closure, nested base qualification, template forward declarations, and namespace
root discovery. No not-found or unresolved-type placeholders remain. The remaining `C4099`,
`C4201`, and `C4309` records are warning-only diagnostics; IDA/Sonar and byte comparison against
the unavailable historical approved header remain separate evidence surfaces.

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
| generated header closure failures | exact manifests plus the complete per-header MSVC audit; optional IDA/Sonar evidence | local acceptance only |
| documentation drift | strict Zensical build in `just check` and source-backed pages | docs CI build |
| graph semantics overclaiming | JSONL projection documented as current; live ingestion on roadmap | knowledge bundle manifest |
