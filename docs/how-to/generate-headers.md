# Generate headers

Use the canonical Typer entry point for reconstruction. The launcher is intentionally thin; the
application layer receives typed requests and the composition root wires concrete infrastructure.

## Single or multiple symbols

Materialize the ELF once before the first generation run. Keep the durable store in the ignored
repository output area so subsequent runs reuse the source-bound manifest:

```powershell
$storeRoot = Join-Path $PWD 'output\analytical-dwarf\main'
uv run ddon-dwarf-reconstructor artifacts materialize-dwarf `
  resources/DDOORBIS.elf `
  --output-dir $storeRoot --write-parquet
$storeManifest = Join-Path $storeRoot 'store-<source-sha16>\manifest.json'
uv run ddon-dwarf-reconstructor artifacts load-doris $storeManifest
```

The load must complete successfully before generation. It publishes a source-bound registry row
after all Doris family counts reconcile; `--dry-run`, an incomplete checkpoint, or a stale
manifest is not a serving publication.

```powershell
uv run ddon-dwarf-reconstructor generate resources/DDOORBIS.elf `
  --dwarf-store $storeManifest `
  --symbol MtObject
uv run ddon-dwarf-reconstructor generate resources/DDOORBIS.elf `
  --dwarf-store $storeManifest `
  --symbol MtObject --full-hierarchy
uv run ddon-dwarf-reconstructor generate resources/DDOORBIS.elf `
  --dwarf-store $storeManifest `
  --symbols-file resources/season2-resources.txt
```

`--symbol` is repeatable for targeted work. Do not combine it with `--symbols-file`; the CLI
rejects the ambiguous request. Use `--full-hierarchy` only when inherited definitions and their
dependencies are part of the requested evidence surface.

When `--symbols-file` requests more than one full-hierarchy root without `--single-file`, the
workflow publishes separate bundles under `output/season2/<platform>/symbols/<index>-<safe-root>/`.
Each bundle has its own `header-bundle.manifest.json`; the root index and symbol name remain in
the manifest metadata. This avoids overwriting same-named headers from unrelated roots. Aggregate
single-directory publication still fails closed when two roots produce conflicting file contents.
Keep failed or incomplete root status in the run report rather than treating the surviving bundles
as a complete corpus.

## Follow up with implementation assembly

Add `--extract-assembly` when the completed header should be followed by method implementation
discovery. The follow-up is deliberately separate and does not change header bytes, ordering, or
the header manifest:

```powershell
uv run ddon-dwarf-reconstructor generate resources/DDOORBIS.elf \`
  --dwarf-store $storeManifest --symbol rLayout \`
  --extract-assembly \`
  --orbis-objdump 'D:\SCE\ORBIS SDKs\8.000\host_tools\bin\orbis-objdump.exe'
```

Add `--llvm-readobj` only when a generic ELF/DWARF structural cross-check is wanted. It is
opt-in and additive; Orbis remains authoritative for PS4 instruction decoding and textual
disassembly:

```powershell
  --llvm-readobj 'C:\msys64\ucrt64\bin\llvm-readobj.exe'
```

For a target-aware, per-method structural comparison, also supply LLVM `llvm-objdump`:

```powershell
  --llvm-objdump 'C:\msys64\ucrt64\bin\llvm-objdump.exe' `
  --llvm-target-triple x86_64-scei-ps4
```

The profile uses `-d -l -C --symbolize-operands` with bounded method ranges. LLVM raw bytes and
addresses are compared with Orbis output and retained in the external cache; the implementation
report stores only slice/status/count/hash summaries. `llvm-readobj` remains generic because it
does not accept `--triple`, and `llvm-tli-checker` is reserved for a future SDK-library/sysroot
diagnostic.

The header publisher completes before the follow-up starts. Reports are then published under
`output/<platform>/implementations/` and retain every source-bound declaration/implementation
candidate, validated code range, header-bundle SHA-256, header-manifest identity, Orbis invocation,
source-line/file-offset provenance, relocation, and resolved or unresolved reference. A missing or
failing Orbis profile does not invalidate the already-published header; its unavailable/empty
status is retained in the report. The report schema is `4.2` and is the canonical implementation
evidence index; complete raw Orbis profile stdout/stderr remains in the source-bound Orbis cache.

Use `--emit-implementation-sources` only with `--extract-assembly` to stage per-method
reconstruction artifacts:

```powershell
uv run ddon-dwarf-reconstructor generate resources/DDOORBIS.elf `
  --dwarf-store $storeManifest --symbol rLayout `
  --extract-assembly --emit-implementation-sources `
  --orbis-objdump 'D:\SCE\ORBIS SDKs\8.000\host_tools\bin\orbis-objdump.exe' `
  --orbis-as 'D:\SCE\ORBIS SDKs\8.000\host_tools\bin\orbis-as.exe'
```

For the single-header `rLayout` workflow the output is:

```text
output/ps4/header-bundle.manifest.json
output/ps4/rLayout.h
output/ps4/implementations/0001-rLayout.json
output/ps4/implementations/0001-rLayout/
  source-bundle.manifest.json
  methods/<stable-method-id>/<stable-method-id>.raw.asm
  methods/<stable-method-id>/<stable-method-id>.s
  methods/<stable-method-id>/<stable-method-id>.o                 # when accepted
  methods/<stable-method-id>/<stable-method-id>.context.json
```

Only a unique DWARF implementation candidate with a valid range and a unique Orbis function
association receives bounded original `.raw.asm` evidence, exact-byte `.s` evidence and, when
`orbis-as` is available, its accepted `.o` object. The `.context.json` packet joins source-bound
Doris context, ABI/CFI, instruction effects, relocations/NIDs, compiler metadata, and explicit
transformation cues. Ambiguous, partial, unsupported, unresolved, deleted, defaulted, pure-virtual,
and unavailable methods remain in the JSON index without invented instructions. The `.s` file is
the handoff artifact for a later agentic C++ translation workflow; the core pipeline does not emit
empty or executable `.cpp` scaffolds. `.raw.asm` is evidence only and is never passed to the
assembler; the context references it instead of duplicating its text.
The report and context packet record structured evidence statuses for ABI and register clobbers,
stack safety, external declarations, and semantic equivalence; absent evidence remains
`not_observed`. MSVC inline assembly is not a validation
target for these PS4 x86-64 artifacts; see [Microsoft's inline assembler guidance](https://learn.microsoft.com/en-us/cpp/assembler/inline/inline-assembler?view=msvc-180)
and [cppreference's compiler-defined asm notes](https://en.cppreference.com/w/c/language/asm).

Use the explicit validator for the evidence dimensions that the scaffold intentionally leaves
open. Supply the complete source-bound analytical store to join method DIEs, parameter locations,
and CFI:

```powershell
uv run ddon-dwarf-reconstructor artifacts validate-implementation <PS4-ELF> `
  --implementation-report <output>/ps4/implementations/0001-rLayout.json `
  --dwarf-store <complete-store-manifest.json> `
  --output-dir $env:TEMP/ddon-implementation-validation `
  --original-addresses `
  --sdk-root 'D:/SCE/ORBIS SDKs/8.000'
```

For this validator, the manifest is only the source-bound Doris publication pin. The method
context is queried from Doris's typed DIE/location/frame families; Parquet and JSONL are not read
directly. Set `DDON_DORIS_SQL_HOST`, `DDON_DORIS_SQL_PORT`, `DDON_DORIS_DATABASE`, and
`DDON_DORIS_TABLE` to the already-loaded publication.

The normal Orbis cache retains only profiles consumed by implementation generation: the symbol
table, bounded disassembly slices, and the standard relocation cross-check. The known-invalid
`-t -T` symbol combination and `-R` dynamic-relocation option are capability-filtered and are
not invoked. The full `--dwarf=info` pass is also not part of this path because Doris is the
authoritative DWARF serving model; its historical timeout is documented once rather than retried.
The complete SCE relocation table is retained as a source/tool/parser-bound JSONL cache; the
report projects only method-relevant entries and stable links to them. An optional LLVM metadata run uses
`llvm-readobj --elf-output-style=JSON --file-header --program-headers --sections --dynamic-table
--relocations --dyn-relocations`. Stdout/stderr files, hashes, return status, duration, and tool
identity remain in the cached report for profiles that actually run. Cache reuse validates the
complete command, flags, tool identity, and captured hashes. SDK subprocesses have no arbitrary
two-minute cutoff; an explicit caller may still provide `--tool-timeout-seconds <seconds>` when a
bounded diagnostic run is required. The implementation validator does not emit per-tool
stdout/stderr files; it keeps only output hashes and concise status/timeout metadata.

When `--llvm-objdump` is supplied, its target-aware slices use `x86_64-scei-ps4` by default and
`-d -l -C --symbolize-operands` plus `--start-address`/`--stop-address`. The report records only
the compact comparison projection; complete LLVM output remains in the source-bound cache. The
target profile is additive and cannot affect Orbis eligibility, header bytes, or assembly selection.

## Latest Season 2 acceptance

The 2026-08-16 rerun of all 289 nonblank roots in
[`resources/season2-resources.txt`](../../resources/season2-resources.txt) published 289/289
header manifests and implementation reports. It checked 2,760 header files and 10,093,364
published bytes with no per-root generation failures. The reports contain 84,553 method rows;
1,150 uniquely eligible methods produced each of `.raw.asm`, canonical `.s`, accepted `.o`, and
`implementation-context/1.0` `.context.json`, with exact raw/report and object/text parity.
The independent host MSVC closure then passed all 2,760 header translation units across the 289
bundles, with zero failures and zero timeouts.

This is clean assembly handoff evidence, not semantic equivalence. The full measured result and
remaining gaps are recorded in the
[`Season 2 acceptance record`](https://github.com/ddon-research/ddon-dwarf-reconstructor/blob/main/specs/001-header-foundation/acceptance-season2-assembly-20260816.md).
The source-bound Doris validator, IDA completeness audit, and machine-readable aggregate audit
remain external artifacts linked from that record; IDA is post-generation cross-validation only.

## What happens inside

1. The composition root constructs a typed `GenerationFacade` and a `GenerationRuntime` with one
  explicit resource scope.
2. `GenerationRuntime` resolves definitions, types, methods, members, and hierarchy information
  from the Doris serving projection; it does not implicitly traverse the ELF or read the
  Parquet/JSONL materialization directly.
3. `HeaderRenderer` renders deterministic declarations with stable ordering and forward
  declarations where required.
4. `AtomicHeaderPublisher` stages the bundle, writes its manifest, and commits or rolls back as a
  unit. A partial, unavailable, or unresolved source-bound full-hierarchy result is recorded as an
  error and cannot publish `UncategorizedDefinitions.h` as a successful bundle.
5. When requested, the committed bundle is handed to a second implementation chain. That chain
  re-traverses method identity and ranges, invokes the retained Orbis profiles, and publishes a
  separate report/source bundle. Its evidence outcome cannot turn a successful header into a
  failed header.

The implementation preserves qualified names, inheritance, field offsets, sizes, source
locations, DIE/CU provenance, and deterministic output ordering. A partial search result is not
complete evidence and must not be consumed as if it were.

## Useful output controls

Use `uv run ddon-dwarf-reconstructor generate --help` for the installed option surface. Keep
generated headers and manifests under `output/` or another explicitly local directory. The
repository does not accept game binaries, generated headers, or runtime caches as source files.

## Troubleshooting order

1. Run `artifacts inspect-dwarf-store <manifest>` to validate the materialized Parquet store and
  source binding.
2. Run `artifacts load-doris <manifest>` and confirm that the registry reports `complete` with
  reconciled family counts.
3. Run `artifacts inspect-elf <path>` to confirm the ELF/DWARF producer facts.
4. Check the run JSONL logs for the `run_id`, symbol, stage, and query evidence status.
5. If a compressed dump is involved, use `artifacts inspect-dwarf-dump <path>` only for an
  explicitly labeled validation cross-check.

If the analytical-dwarf Compose stack is healthy but generation reports a refused Doris
connection, verify the host-side FE mapping before concluding that Doris is unavailable. The
application default is `127.0.0.1:9030`; a workstation can publish the container's canonical
`9030` on another host port such as `19030`. Check `docker compose --file
ops/analytical-dwarf/compose.yaml ps --all` and the exact endpoint with
`Test-NetConnection 127.0.0.1 -Port 19030`, then align the application environment:

```powershell
$env:DDON_DORIS_SQL_HOST = '127.0.0.1'
$env:DDON_DORIS_SQL_PORT = '19030'
$env:DDON_DORIS_DATABASE = 'dwarf'
```

A refusal at `9030` proves only that the configured endpoint is wrong or closed. Confirm the SQL
handshake and a bounded `SHOW TABLES` query on the published host port before recording the
backend as unavailable. The connection adapter reports the exact host, port, database, and user
it attempted; it does not silently probe a second endpoint.

Do not delete a warm source-bound cache as routine cleanup. Repair and purge commands are
explicit and narrowly targeted.
