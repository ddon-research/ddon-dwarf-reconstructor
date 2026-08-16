# CLI reference

The supported entry point is:

```powershell
uv run ddon-dwarf-reconstructor [OPTIONS] COMMAND [ARGS]...
```

| Command | Purpose |
| --- | --- |
| `generate` | Generate deterministic C++ headers for one or more symbols. |
| `export-knowledge` | Export deterministic evidence as a knowledge bundle. |
| `artifacts` | Inspect and maintain source catalogs, indexes, caches, and tool evidence. |
| `performance` | Collect opt-in resource/profiler evidence and maintain benchmark history. |

## Generation and export

```powershell
uv run ddon-dwarf-reconstructor generate --help
uv run ddon-dwarf-reconstructor export-knowledge --help
```

Common inputs are an ELF path, one or more `--symbol` values or a `--symbols-file`, an optional
`--full-hierarchy`, and an output directory. Use the help surface from the locked environment for
the complete option list; this page intentionally documents stable commands rather than copying
Typer's formatting.

Normal generation and knowledge export require a source-bound `--dwarf-store` manifest whose
complete projection has been loaded into Doris with `artifacts load-doris`. The manifest is
produced and published explicitly before lookup; missing, stale, incomplete, unavailable, or
source/count-mismatched stores fail closed. These commands query Doris only; Parquet remains the
canonical materializer output and JSONL remains an opt-in audit/interchange projection.

For a complete local store, the repository convention is
`output/analytical-dwarf/main/store-<source-sha16>/manifest.json`. Checkpoints and bounded probes
belong under `%TEMP%\ddon-analytical-dwarf` and require explicit incomplete-evidence flags.

`generate --extract-assembly` starts a separate chain only after the header bundle is committed.
Add `--emit-implementation-sources` to publish exact-byte `.s` files and, when `orbis-as` is
available, `.o` objects for unique DWARF-to-Orbis matches; the option requires
`--extract-assembly`. Pass `--orbis-as <path>` explicitly when the assembler is not beside
`--orbis-objdump`; the sibling SDK assembler is discovered otherwise. The JSON report retains
all candidates, consumed profile invocations, raw
method disassembly, instruction references, and source/file offsets. The canonical source-emission
layout is:

```text
<output>/<platform>/implementations/<index>-<symbol>.json
<output>/<platform>/implementations/<index>-<symbol>/
  source-bundle.manifest.json
  methods/<stable-method-id>/<stable-method-id>.raw.asm
  methods/<stable-method-id>/<stable-method-id>.s
  methods/<stable-method-id>/<stable-method-id>.o                 # when accepted
  methods/<stable-method-id>/<stable-method-id>.context.json
```

The report is the evidence authority. The bundle manifest is only an atomic-publication and
integrity envelope. The report is schema `4.2`; the bundle manifest is schema `3.1`. Each eligible
method may have a bounded `.raw.asm` evidence file, canonical `.s` compiler input, accepted `.o`,
and `.context.json` AI transformation/provenance packet. `.raw.asm` is never passed to
`orbis-as`; `.context.json` references it instead of duplicating the raw text. The source bundle
is not part of the header manifest or MSVC header-closure validation. The core pipeline does not
emit empty or executable `.cpp` placeholders; C++ translation is a later agentic workflow.

The implementation report schema is `4.2`. Normal Orbis generation retains only the symbol,
bounded disassembly, and standard-relocation profiles. The known-invalid `-t -T` combination and
`-R` dynamic-relocation option are capability-filtered and are not invoked. The full
`--dwarf=info` pass is not needed because Doris is the authoritative DWARF serving model; its
historical timeout is documented rather than retried. SCE dynamic metadata is decoded by the
source-bound reader and complete entries stay in its producer cache. Add `--llvm-readobj <path>` for the opt-in generic cross-check using
`--elf-output-style=JSON --file-header --program-headers --sections --dynamic-table --relocations
--dyn-relocations`. LLVM never replaces Orbis instruction evidence or SCE relocation decoding.

Add `--llvm-objdump <path>` to run the independently cached, per-method LLVM disassembly
cross-check. It uses `--triple=x86_64-scei-ps4 -d -l -C --symbolize-operands` plus method-range
flags; `--llvm-target-triple` changes the requested triple explicitly. For `generate`, these
options require `--extract-assembly`; knowledge export may attach them through its Orbis evidence
path. `llvm-readobj` has no triple interface and is recorded as generic metadata
evidence (`target_status=not_applicable`). `llvm-tli-checker` is not an ELF extraction tool.

The Orbis report/cache schema is `2.4` with parser identity `orbis-objdump-text-v7` and SCE
metadata parser `orbis-sce-metadata-v3`. The report
records the typed SDK-definition identity, while raw LLVM/Orbis stdout and stderr remain
authoritative in the source-bound cache.

Use the explicit read-only validator for the remaining implementation dimensions:

```powershell
uv run ddon-dwarf-reconstructor artifacts validate-implementation <elf> `
  --implementation-report <output>/ps4/implementations/0001-rLayout.json `
  --dwarf-store <complete-analytical-store>/manifest.json `
  --output-dir $env:TEMP/ddon-implementation-validation `
  --original-addresses `
  --sdk-root 'D:/SCE/ORBIS SDKs/8.000'
```

The validator requires either `--original-addresses` or an explicit aligned `--load-base`. It
publishes independent relocation, opaque/source-bound/community-candidate NID, ABI/CFI, instruction-safety, Orbis
assembler/objdump, and static-parity statuses. It emits canonical `.s`/`.o` evidence through the
external validation directory; C++ files are not generated by this pipeline.
No method `.cpp` files are generated; when an Orbis compiler is supplied, the separate ABI probe
matrix may retain its eight small probe inputs as compiler evidence.
CFG/external-edge parity remains `not_observed` when `orbis-objdump` is unavailable; live PS4
behavior remains `not_observed` unless separately evidenced.
`--orbis-readelf` may be supplied (or resolved from `--sdk-root`) to retain target-object
header/section/relocation metadata. `--orbis-objdump` enables normalized generated-object branch
and call-edge comparison, and `--orbis-ld` optionally records a relocatable link result. A
complete source-bound `--dwarf-store` is required for
method-specific location and CFI evidence. For this command, the manifest is a publication
identity and source-binding anchor, not a row-reading input: the validator opens the complete
source publication through Doris and queries the normalized `die`, `attribute`, `reference`,
`range`, `location`, and `frame` families. It never opens the Parquet or JSONL projections.
Configure the existing Doris endpoint with `DDON_DORIS_SQL_HOST`, `DDON_DORIS_SQL_PORT`,
`DDON_DORIS_DATABASE`, and `DDON_DORIS_TABLE`; a missing or count-mismatched registry row makes
the analytical model unavailable and prevents ABI/CFI promotion.
Use `--tool-timeout-seconds <positive-seconds>` only when the caller wants an explicit limit for
each SDK compiler, assembler, metadata, or linker invocation. Without it, implementation
validation imposes no arbitrary tool timeout. It retains tool identity, command, output hashes,
and concise statuses; raw per-tool stdout/stderr files are not emitted.

Use `--nid-database` `<path>` to supply a JSON or two-column mapping. A file named aerolib.csv, or
a mapping whose provenance authority is community_reference, is retained as external candidate
evidence rather than official NID authority. Supply `--nid-database-provenance` `<manifest.json>` to
bind the local mapping to its source URL, full commit, file SHA-256, and known 16-byte NID suffix.
Only a community mapping with complete pinned provenance plus matching NID hash and encoded
library/module context becomes community_verified; candidates, mismatches, and unavailable
context cannot satisfy target-object-equivalent. The current validation report schema is 4.1;
the dated 4.0 reports remain historical evidence.

The analytical model is deliberately columnar-engine oriented. The one-time materializer writes
typed family columns and the loader publishes them into Doris; method validation then uses
source/offset equality predicates, projected columns, and a server-side CFI range-overlap query.
Do not rerun the hours-long materializer for validation or add a file-backed runtime fallback.

For an independent completeness check after generation, use the isolated IDA audit:

```powershell
uv run ddon-dwarf-reconstructor artifacts audit-implementation-coverage `
  --implementation-report <implementation-report.json> `
  --ida-c-dump <ida-export.c> `
  --elf <source.elf> `
  --output-dir $env:TEMP/ddon-implementation-audit
```

This command reads the existing report and optional IDA C dump, writes an external audit artifact,
and reports name/body coverage and possible scope gaps. It never changes Doris targets, production
names or addresses, caches, compiler inputs, or implementation statuses. An IDA body absence is
not evidence that a method is absent.

The full 2026-08-16 Season 2 acceptance covered 289 roots, 2,760 header files, and 1,150 clean
assembly bundles. Independent MSVC closure passed all 2,760 header translation units with zero
failures and zero timeouts. It is recorded as `observed-partial`: artifact and Orbis assembler
acceptance are observed; the static validator separately observed relocation and opaque NID
identity, while method association, ABI/CFI, instruction safety, static parity, and live behavior
remain independently reported. See the
[`Season 2 acceptance record`](https://github.com/ddon-research/ddon-dwarf-reconstructor/blob/main/specs/001-header-foundation/acceptance-season2-assembly-20260816.md)
for the exact counts and external audit artifacts.

## Artifact subcommands

```text
inspect
verify-source
inspect-elf
inspect-dwarf-dump
materialize-dwarf
inspect-dwarf-store
load-doris
list-tool-profiles
probe-tool
export-tool-evidence
validate-implementation
audit-implementation-coverage
repair-dump-index
rebuild-dump-index
repair-catalog
repair-symbol-cache
purge-dump-index
```

Every maintenance command has an explicit target and confirmation contract. Use
`uv run ddon-dwarf-reconstructor artifacts --help` and the individual subcommand help before
operating on a large or durable artifact.

## Performance subcommands

```text
doctor
profile <elf>
compare-runtimes <elf>
profile-index <dump>
benchmark-dwarf-store <elf>
benchmark-doris-current <elf>
benchmark-doris-optimization <elf>
benchmark-doris-flight
check-doris-flight
profile-dwarf-store <elf>
benchmark
history compare
history export
```

See the [performance reference](performance.md) for profiler choices, metric status semantics,
raw artifact boundaries, and the v1 history schema.

`benchmark-dwarf-store` accepts `--run-knowledge-export` for explicit complete export evidence;
the command writes the generated bundle and its deterministic tree hash under the external
benchmark artifact directory. For a database already loaded from the complete manifest, combine
`--query-existing-doris` to measure serving queries without reloading the canonical files or
rescanning the full Parquet projection.

`profile-dwarf-store` wraps that same benchmark through the shared performance runner. Use
repeatable `--profiler scalene` and `--profiler cprofile` options for line/memory and method CPU
evidence before changing Doris keys, indexes, buckets, or materialized views. Add
`--profiler scalene-libraries` for an optional standard-library/site-package comparison; it is a
broad diagnostic and is not included in `--profiler all`. The child benchmark report remains
separate from the profiler manifests.

`benchmark-doris-current` reuses a complete source-bound publication. The
`benchmark-doris-optimization` command adds redacted generation query tracing, typed serving-variant
identity, selective-statistics policy, and one-factor lookup/physical candidates. Runtime-only
variants such as `typed-projections`, `reference-prefetch-lazy`, and
`targeted-child-tag-filter` reuse the canonical tables; lookup candidates require explicit
`--provision-candidate`. No candidate changes the canonical fourteen-family contract. Use the
command's `--help` surface for the cold/warm repetition and profile-budget controls.

To repeat the measured interaction batch of all positive standalone candidates, use
`--candidate combined-positive-below-gate --provision-candidate`. It activates lazy reference
prefetch, the decoded-serving projection, and source/name lookup buckets 2/4/8 with b8 active;
the other buckets are provisioned as comparison-only alternatives. The measured batch is now the
promoted generation serving path. Normal canonical loading creates and refreshes
`dwarf_records_opt_name_b8`, and normal generation uses lazy prefetch and the serving projection
without environment switches. Raw attribute columns remain retained in Doris for exact evidence;
the historical 2026-08-10 Season 2 run validated the narrowed generation projection for all 289
roots. A post-boundary-refactor rerun must establish fresh parity before this claim is current.

For per-header compiler acceptance, run the external MSVC validator against each published bundle
root. It creates one translation unit per header and writes the structured report outside the
repository; warning-only diagnostics are retained while compiler failures are non-zero evidence:

```powershell
uv run python -m tools.sonar.validate_header_bundle `
  --input-root $env:TEMP/ddon-analytical-dwarf/season2-msvc-fix4-20260810-input `
  --validation-directory $env:TEMP/ddon-analytical-dwarf/msvc-season2-fix4-20260810
```

This validator is a change-triggered acceptance tool, not part of normal generation. A clean
compiler report proves syntax and generated-closure integrity; it does not replace source-bound
manifest checks, ordered-output hashes, or separate IDA/Sonar evidence.

The 2026-08-09/10 complete-store run measured the live generator path. Bounded source/unit-aware
hydration produced exact exhaustive `rAIFSM` output; the post-policy canonical run measured
`16.1152/16.1187 s` warm p50/p95 for the promoted combined path, versus
`19.1208/19.1271 s` for the prior canonical path. Child-frontier/reference prefetching and
line-program caching are included in the serving algorithm. The canonical fourteen-family schema,
keys, indexes, storage, and registry row contract remain unchanged; the b8 auxiliary table is
created and populated during canonical load. The targeted child-tag filter regressed warm p50 by
10.5% and is rejected. MV, index, bucket, storage-format, session, and Stream Load variants remain
`not_observed` unless their trace gate is met. This command is a reusable, change-triggered
one-shot regression/promotion tool, not a continuous service.

`DDON_DORIS_HYDRATION_SCOPE=global` is the canonical setting. A fair-path `unit` screen preserved
exact `rAIFSM` output but took `289.048 s` versus the canonical `19.121/19.127 s` warm p50/p95;
its partial trace showed 26,463 observations and is recorded as a rejected query-fan-out
candidate, not a serving default.

`check-doris-flight` is the explicit preflight for the optional Flight SQL overlay. It records
Compose-file and rendered-configuration hashes, FE/BE endpoint reachability, and bounded startup
log markers. Run it with `uv run --group flight-sql` before
`benchmark-doris-flight`; the latter compares the default PyMySQL row path with ADBC qmark queries,
Arrow table/RecordBatch consumption, a reducer, and bounded hydration batches. Neither command
changes the default MySQL/DDL/Stream Load path. Because the current Doris producer rejects prepared
statement parameter exchange, the benchmark-only
`--allow-unparameterized-flight-fallback` flag can be combined with
`--reused-connections-only` to render checked literals for a diagnostic run; its report remains
`partial` and is not a runtime fallback.
