# External tool evidence

The reconstructor treats external inspection programs as one-time producers of durable evidence,
not as hidden runtime dependencies. A local tool is first captured with bounded `--version` and
`--help` output. A named profile then streams one output file for an immutable ELF/DWARF source.
The manifest records source identity, tool identity, profile arguments, output checksum, producer
authority, and deterministic artifact key.

## Adoption matrix

| Producer | Local/useful commands | Adopted profile | Authority | Boundary |
| --- | --- | --- | --- | --- |
| Sony Orbis SDK 12.000 (promoted) and SDK 8.000 (historical, explicit) | `orbis-clang++`, `orbis-as`, `orbis-ld`, `orbis-readelf`, `orbis-objdump`, `orbis-bin`, `orbis-nm`, `orbis-addr2line`, `orbis-llvm-mca` | `orbis-bin-stack-sizes`, `orbis-bin-dynamic-symbols`, `orbis-bin-inline-relocations`, `orbis-bin-section-headers`, `orbis-bin-memory-layout`, `orbis-bin-file-layout`, `orbis-abi-probes`, `orbis-target-object`, `orbis-elf-headers`, `orbis-symbols` | PS4 ABI/SCE, target acceptance, symbols, and additive utility views | SDK 12 is the default host profile; SDK 8 requires an explicit path. Preserve exact target, flags, tool hashes, and mixed-family rejection |
| LLVM | `llvm-readobj`, `llvm-readelf`, `llvm-objdump`, `llvm-dwarfdump`, `llvm-debuginfo-analyzer` | `llvm-elf-metadata-relocations-json`, opt-in `llvm-ps4-disassembly`, `llvm-dwarf-statistics`, `llvm-dwarf-verify`, `llvm-debug-info-summary` | Generic ELF/DWARF and target-aware structural cross-check | Keep unknown SCE values and do not overwrite Orbis facts |
| GNU Binutils | `readelf`, `objdump`, `nm` | `gnu-elf-headers`, `gnu-symbols` | Generic ELF/symbol cross-check | GNU target naming can omit Orbis-specific ABI semantics |
| elfutils | `eu-readelf`, `eu-elflint` | `elfutils-elflint` | Generic integrity diagnostics | Diagnostics are not reconstructed layout |
| libdwarf | `dwarfdump` | `libdwarf-check-summary`, `libdwarf-check-all`, `libdwarf-producers` | DWARF integrity/producers | Summary is bounded; full output is capped and fails closed if oversized |
| pyelftools | In-process `ElfDwarfSession`/ELF evidence | Existing typed adapters | Structured parser foundation | No subprocess export; session owns normalization and handles |
| LIEF | Optional Python/C++ parser | Not in runtime dependency set | Exploratory comparison | Validate PS4 custom types/segments before adoption |
| OpenOrbis/readoelf | Reference source and Orbis ELF readers | Reference only | Comparative implementation evidence | Keep source/provenance; do not silently replace Sony output |
| elfldr | Loader/payload research | Not adopted | None for offline inspection | Never execute or ingest loader behavior in this workflow |

## Local SDK 12 CPU/ABI contract

The promoted `OrbisToolchainContract` is `orbis-sdk12-llvm18` for SDK `12.000`. It records the
observed compiler/assembler/linker/`llvm-mca` identities, `x86_64-scei-ps4` target, AT&T syntax,
LLVM integrated-assembler default, PIC/function-data-section/CFI/aranges/frame-pointer/visibility
defaults, and the reviewed ABI deviations for hidden structure returns, variadic `__m256`,
`__int128`, stack alignment, register classes, and TLS. It also records
`EF_FFUNC_DATA_SECS_ENABLED=0x04000000`, `R_X86_64_ORBIS_GOTPCREL_LOAD=0x28`, and
`.sce_stack_sizes` as typed ELF observations. SDK 8 remains an explicit historical contract; a
host-tool contract does not establish the build SDK of the inspected ELF.

The contract records local documentation provenance without copying proprietary text:

```text
D:\SCE\ORBIS\documentation\chm\en\extracted\en\System\Compiling_Linking_and_Building\CPU_Assembler-Guidelines
D:\SCE\ORBIS\documentation\chm\en\extracted\en\System\Compiling_Linking_and_Building\CPU_Compiler_ABI-Overview
D:\SCE\ORBIS\documentation\chm\en\extracted\en\System\Generating_and_Using_Dynamic_Libraries\Sysmodule-Reference\ps4-module-ids.html
D:\SCE\ORBIS\documentation\chm\en\extracted\en\System\Analysis_and_Debugging\Machine_Code_Analyzer-Overview\analyzing-assembly-code-generated-by-the-compiler.html
```

`orbis-bin` profiles are source-bound and additive. SDK 12 `orbis-bin --help` validates `-r` as
the relocation display option; GNU objdump-only flags are not included in the inline-relocation
profile. `orbis-objdump` remains the canonical disassembler until a separately retained
disassembly comparison proves a replacement safe.

## PS4 authority matrix

The implementation chain keeps three deliberately separate authorities:

| Evidence | Authority | Use | Boundary |
| --- | --- | --- | --- |
| x86-64 instruction decoding, PS4 demangling, and textual disassembly | Matching Orbis binutils | Canonical method ranges, bytes, operands, and names | Tool/version-specific output; no ABI or semantic inference |
| ELF/DWARF structure and generic dynamic-table cross-check | LLVM 22.1.8 `llvm-readobj` (opt-in) | Confirm headers, sections, program headers, dynamic tags, and conventional relocation views | Generic ELF interpretation cannot replace SCE or Orbis semantics |
| SCE dynamic tags, `PT_SCE_DYNLIBDATA`, and 24-byte RELA tables | In-repository `OrbisSceMetadataReader` | Decode PS4 relocation descriptors and source-bound relocation entries | Never applies relocations or synthesizes declarations |
| Canonical assembly/object acceptance and normalized object edges | Orbis SDK `orbis-as`/`orbis-ld`/`orbis-objdump` | Produce `.s`/`.o`, optional relocatable link, and independent CFG/call-edge evidence | Missing tools leave compiler or parity dimensions `not_observed`; bytes alone do not prove equivalence |

The optional target-aware LLVM profile is independently cached per method range. Its command is:

```text
llvm-objdump --triple=x86_64-scei-ps4 -d -l -C --symbolize-operands
  --start-address=<start> --stop-address=<stop> <elf>
```

`llvm-objdump` raw bytes are retained in the external evidence cache and compared by address and
bytes with the canonical Orbis slice. The implementation report stores only the requested/effective
triple, capability/availability status, cache identities, slice counts, and comparison totals.
LLVM output is never promoted to the instruction authority. `llvm-readobj` remains a generic
metadata profile because its local command surface has no `--triple` option; its triple status is
therefore `not_applicable`. `llvm-tli-checker` is not part of ELF extraction: it diagnoses target
library availability and needs an explicit SDK library/sysroot input.

`performance analyze-assembly` is a separate `orbis-llvm-mca` workflow. It accepts only marked
post-compile assembly regions, retains input/tool/output hashes and marker names, and reports
performance-model evidence independently. Its result cannot satisfy compiler ABI, object parity,
relocation, or semantic-equivalence dimensions.

The upstream [ps4_module_loader metadata definitions](https://github.com/SocraticBliss/ps4_module_loader/blob/657f9d380abfec9097bc4bddbc63551b3cd5e47b/ps4_module.py#L325-L363)
and [relocation parser](https://github.com/SocraticBliss/ps4_module_loader/blob/657f9d380abfec9097bc4bddbc63551b3cd5e47b/ps4_module.py#L1141-L1157),
together with the [GhidraOrbis ELF header](https://github.com/astrelsky/GhidraOrbis/blob/2d6e3fac23ae9830e941c32826e97100ed603311/src/main/java/orbis/elf/OrbisElfHeader.java),
are research references for the SCE table layout. They are not runtime dependencies.

## Evidence contract

`ToolchainExporter` writes a versioned manifest and raw output under a content key. Reuse requires
validating the manifest schema, content key, source hash/size, output path confinement, output size,
and output SHA-256. Knowledge export accepts only complete manifests through repeated
`--tool-evidence` options. It emits additive `Tool`, `SourceArtifact`, and `Evidence` records and
retains the authority label; it does not mutate `Type`, `Field`, `Method`, producer, or source
location facts from DWARF.

Raw output is intentionally not parsed at every lookup. Index or graph ingestion should resolve
the `artifact_key` through the manifest catalog, inspect the producer-specific format, and retain
the original bytes. This keeps cold external scans separate from warm deterministic lookups and
allows an evidence producer to be replaced only by a new source/tool/profile identity.

## PS4 observations

On the Windows development host, the LLVM verifier is run from the MSYS2 UCRT64 profile:
`C:\msys64\ucrt64.exe` resolves to `C:\msys64\ucrt64\bin\llvm-dwarfdump.exe` (LLVM 22.1.8).
For captured non-interactive output, the equivalent profile environment is `MSYSTEM=UCRT64` with
`/ucrt64/bin` on the MSYS2 shell `PATH`. `--verify`, `--verify-json`, and `--statistics` are
explicit evidence commands; their diagnostics do not replace the source-bound materializer.

The local PS4 ELF is ELF64 little-endian x86-64 with `ELFOSABI_FREEBSD`, Sony type `0xfe10`, and
SCE program-header values in the `0x61000000` range. Orbis `objdump -f` reports
`elf64-x86-64-freebsd`; generic LLVM/GNU readers accept the file but report generic x86-64 and
unknown/LOOS SCE values. This is why generic exports are cross-checks rather than ABI authority.

The typed Orbis definition subset is reproduced from the local SDK6500/n267 source package. It
records `PT_SCE_DYNLIBDATA`, `PT_SCE_PROCPARAM`, `PT_SCE_COMMENT`, `PT_SCE_LIBVERSION`, the useful
`DT_SCE_*` table, `R_X86_64_ORBIS_GOTPCREL_LOAD` (code 40, four-byte signed 32-bit PC-relative),
the `x86_64-orbis-freebsd9` configure identity, and 0x4000 page-size facts. The official source
does not define `PT_SCE_RELRO`; standard `PT_GNU_RELRO` is retained separately. The source file
hashes are part of the SDK-definition identity in cache keys and reports.

Use the goal handoff record to distinguish confirmed command output, approximate tool behavior,
blocked SDK/container prerequisites, and unresolved C++ semantics. Declarations and debug metadata
do not prove method bodies; disassembly remains a separate evidence producer. For generated
headers, `generate --extract-assembly` consumes the completed header bundle in a follow-up chain.
A symbol request performs one union discovery and writes `implementation-report.json` at
`generated/ps4-<client-version>/` (or its explicit output root), with flat resource/shared `.asm`
evidence when context generation is enabled. Use `--no-generate-context` for an assembly-only
handoff without generation JSON.
The implementation-discovery report (schema `4.2`) is the canonical projection of method-range evidence: it
preserves all candidates, exact raw method text, selected Orbis instructions, instruction-owned
references, source/file offsets, and consumed tool invocation metadata. The optional source bundle
contains bounded `.raw.asm` evidence, exact-byte `.s` compiler input, SDK-produced `.o` objects
when accepted, and `.context.json` AI transformation/provenance packets, plus a minimal
publication envelope. `.raw.asm` is never assembler input, and the core pipeline does not emit
placeholder `.cpp`, reference, or diagnostic files. A later agentic workflow may translate the
assembly. The separate implementation-validation report is schema `4.4` and also carries the
deterministic DWARF target manifest, scope policy/hash, retained ELF function candidates, range/name
match reasons, and range provenance. Missing, partial, ambiguous, and unsupported association
evidence is retained as status rather than promoted to a body match. Its typed
static-equivalence disposition is `not_promoted`, `target_object_equivalent`, `conflicting`, or
`failed`; legacy 4.3 payloads default to `not_promoted` during read.

## Validated handoff record

The PS4 `02020005` fixture has schema-1.1 exports for Orbis headers, LLVM JSON metadata, and the
libdwarf check summary. Their artifact keys are respectively
`696180705efd088147a1f83d5a4884fee9fa64bb36843610276d5fef63d42d70`,
`1a0e0536308627088e93dfffff43d1a4446b16384f92ff052bc413c3005a7182`, and
`fb52d4d01590587bc835de31ad7175714d363390a85215775115b7dff3f9b58c`. A warm rerun reused the
validated keys, and knowledge export projected all three as additive tool evidence. Raw outputs
remain under ignored local output directories and are joined by manifest key rather than copied
into every lookup.

The generic Compose image built and its LLVM JSON probe preserved `FreeBSD` OS/ABI and Sony type
`0xFE10`. This confirms container compatibility for inspection, not PS4 ABI authority; Orbis host
tools remain the matching-SDK authority.

The normal implementation chain uses only the profiles whose output is consumed: `-t -C -w
--special-syms` for symbols; `-EL -d -l -F -C -w --prefix-addresses --show-raw-insn` for bounded
disassembly; and `-r` for the Orbis relocation display. The known-invalid
`-t -T` combination and `-R -C -w -F` dynamic-relocation option are capability-filtered and are
not invoked. The full `--dwarf=info` pass is not part of generation because Doris is the
source-bound DWARF serving authority. The historical SDK observations are retained here as
documentation, not as per-run unavailable diagnostics. Conventional Orbis relocation output is
empty, while PS4/SCE relocation metadata is present and decoded through the source-bound SCE
metadata reader. The observed SCE tables use
`DT_SCE_RELASZ / DT_SCE_RELAENT = 172404` and `DT_SCE_PLTRELSZ / DT_SCE_RELAENT = 539`, for
`172943` cached entries. Direct/indirect calls, branches, RIP-relative data references such as
`rLayout::DTI` and the stack guard, relocation rows, source lines, discriminators, and file
offsets remain structured evidence. They do not authorize synthesized `extern` declarations.

The target-aware LLVM profile is additive and opt-in. A missing executable, failed capability
probe, unsupported triple, or partial slice is retained as explicit evidence and cannot
change Orbis eligibility, header bytes, or generated assembly selection. The current profile
uses `x86_64-scei-ps4` whenever `llvm-objdump` is supplied; a different triple changes the
source-bound cache key and is recorded as a separate comparison.

## Implementation-generation validation boundary

The read-only command `artifacts validate-implementation` is the promotion boundary for static
target-object evidence. It requires an explicit original-address or load-base policy and records
the source hash, implementation-report hash, SDK-definition identity, relocation evaluator
version, load-image geometry, target bytes, opaque NIDs, CFI/effect summaries, compiler tool
hashes, and per-method context packets. No C++ view is generated; canonical assembly and objects
are emitted only in the external validation directory. `orbis-objdump` is
required to observe normalized CFG/call-edge parity; `orbis-ld` is optional. Live PS4 behavior
remains a separate `not_observed` dimension.

The implementation validator is deliberately an optional feature boundary. Its command, strict
report projection, compiler-probe entry point, and context adapter are exposed below
`infrastructure/validation`, which delegates to the dedicated strict evidence adapters; generation
and artifact publication consume only the neutral context enrichment contract. Removing that
feature later therefore removes a downstream evidence path, not validation imports from header
rendering or method discovery.

When `--dwarf-store` is supplied, implementation validation uses the
`DorisImplementationEvidenceModel`. The manifest is read for source/schema/publication identity
and the complete registry is checked; method DIEs, locations, and CFI are then queried from
Doris's typed family tables. Parquet and JSONL are producer/audit projections and are not read by
this validator. The one-time materializer and native load therefore remain the expensive
preparation boundary, while the validation model uses column projection, source/offset keys, and
server-side CFI overlap predicates.

The implementation-validation context is a bounded logical Doris projection, not a second file
store. Requests are ordered by stable method key and batched at 512. Each batch fetches method and
formal-parameter DIEs, object-pointer reference targets, required typed attributes, locations, and
the CFI envelope; a read-only context view then serves the existing evidence logic without
per-method round trips. Relocations and relocation-ID/NID bindings are indexed once per run. The
batch summary is retained as one aggregate diagnostic; individual query retries, raw
implementation tool streams, and timeout noise are not bundle artifacts. The implementation
validator accepts the explicit `--tool-timeout-seconds` option; when unset it imposes no tool
timeout, and an actual timeout records only tool, stage, elapsed time, configured limit, and
output/status hashes.

The projection also normalizes the Doris location-family `expression_json` column into the logical
expression used by ABI transformation cues and carries the resulting ABI-facts map into each
validation context packet. This correction is covered by focused tests and a bounded live Doris
probe; the earlier full-corpus report remains the batching baseline until the next representative
gate is run.

The 2026-08-16 `rLayout` acceptance produced 26 deterministic `.raw.asm`/`.s`/`.o`/
`.context.json` method bundles from 28 bounded target functions. Raw/report hashes and all 26
object `.text` sections matched exactly, while the Doris validator still reported method-specific
ABI, safety, compiler, and parity gaps independently. The accepted objects therefore remain a
clean assembly handoff, not a semantic-equivalence claim. The exact report, bundle, validator, and
IDA-audit hashes are retained in the feature acceptance record; the IDA artifact remains a
cross-validation-only result.

The full 2026-08-16 Season 2 run extended this evidence to all 289 resource roots: 2,760 header
files were checked, 84,553 method rows were retained, and 1,150 methods produced complete
`.raw.asm`/`.s`/`.o`/`.context.json` handoff bundles. The first concurrent pass exposed a
JSON tuple/list SDK-identity cache mismatch; canonical comparison plus a versioned disassembly
cache key fixed it, and the affected `rLoadingParam` root was rerun with 172,943 observed SCE
relocations and no diagnostics. This cache repair is source-pipeline evidence, not an ABI or
semantic-equivalence result. The independent MSVC closure passed 2,760/2,760 header units with
zero failures and zero timeouts. The pre-batching Doris validator was stopped without promotion
after exposing the per-method query/rescan gap. After the bounded projection/index change, the
retained `rLayout` pilot published an atomic schema-4.0 report for 1,037 methods in approximately
28.6 seconds, and the full 1,150-method Season 2 validator published an atomic failed report in
approximately 85.8 seconds. Its context summary was 3 batches and 1,150 requests; relocation and
opaque NID evidence were observed for all methods, while ABI, compiler, effects, and parity
remained independently gated. The report is retained outside the repository at
`C:\Users\morph\AppData\Local\Temp\ddon-implementation-validation-season2-20260816-batched\implementation-validation-4236f598acc8f158.json`
with SHA-256 `97a83535c366f2b8d7e6015fda7f2a9177fda45d1b0621402ba79e77552ac71b`.

## IDA completeness audit boundary

`artifacts audit-implementation-coverage` is a read-only, post-generation audit. It may compare
the production report with an optional IDA C dump to identify exact/normalized name coverage,
methods with an IDA body but no generated disassembly, overloaded-name ambiguity, and possible
scope or association gaps. It never supplies discovery targets, names, addresses, ranges, cache
inputs, compiler inputs, or status promotion. An absent IDA body is not evidence that a DWARF
method is absent; every discrepancy is a diagnostic against the DWARF/ELF algorithm.

The following external references were reviewed and recorded at fixed commits. No source or
runtime dependency is vendored:

| Reference | Commit, path, license | Adopted concept | Authority boundary |
| --- | --- | --- | --- |
| [GhidraOrbis](https://github.com/astrelsky/GhidraOrbis/blob/2d6e3fac23ae9830e941c32826e97100ed603311/src/main/java/orbis/elf/OrbisElfHeader.java) | `2d6e3fac23ae9830e941c32826e97100ed603311`; `src/main/java/orbis/elf/OrbisElfHeader.java`; repository `LICENSE`, GPL-3.0 | Sectionless ELF handling, SCE e-type recognition, dynamic-table address/file mapping, symbol/relocation discovery, and exception-frame identification | Java/Ghidra memory mutation, rebasing, and loader assumptions are not imported; SDK/BFD and source-bound ELF evidence remain authoritative. |
| [SocraticBliss ps4_module_loader](https://github.com/SocraticBliss/ps4_module_loader/blob/657f9d380abfec9097bc4bddbc63551b3cd5e47b/ps4_module.py) and [aerolib.csv](https://github.com/SocraticBliss/ps4_module_loader/blob/657f9d380abfec9097bc4bddbc63551b3cd5e47b/aerolib.csv) | 657f9d380abfec9097bc4bddbc63551b3cd5e47b; ps4_module.py, aerolib.csv; repository LICENSE, GPL-3.0 | 24-byte RELA layout, SCE dynamic tags, segment/base candidates, packed module/library identity fields, and an external NID-name candidate mapping | IDA address mutation, calling-convention settings, and community NID names do not establish PS4 ABI or official NID authority. The validator may ingest a locally hashed, source-pinned map, but promotes it only after NID hash and library/module context checks. |
| PS4 SDK 8.0 | Local `D:\SCE\ORBIS SDKs\8.000`; `license/src_package/binutils-orbis-2_22_1-src-SDK6500-n267/binutils/include/elf/common.h`, `x86-64.h`, `bfd/elf64-x86-64.c`, `README-ORBIS`; Sony SDK license terms apply | `orbis-clang++`, `orbis-as`, SDK target triple, BFD relocation names/formulas, SCE tags, page/alignment facts, and code `0x28` definition | SDK files are never copied into the repository; the SDK does not provide a complete NID-name authority, and code `0x28` remains unresolved until instruction-patching semantics are independently verified. |

The source-bound implementation report now retains these identities as adopted concepts and
keeps the authorities distinct: SDK/BFD definitions for ELF facts and compiler acceptance,
while the community aerolib mapping is retained as external NID-name candidate evidence only.
When supplied to the validator, the local mapping path and SHA-256, source URL and commit,
provenance manifest, and optional NID suffix are recorded. Hash or encoded library/module
conflicts fail closed; an unverified community name cannot promote target-object-equivalent.
Orbis objdump for PS4 instruction decoding, the SCE reader for metadata discovery, and the
validator for pure relocation application/effect evidence.

## SDK 12 full-root disassembly refactor evidence

The source-bound SDK `12.000` baseline/post acceptance is retained outside source control at
`C:\Users\morph\AppData\Local\Temp\ddon-disassembly-refactor-20260818`. It used the complete
analytical store, the immutable ELF SHA-256
`4236f598acc8f15893181455ed195e39dfa4dbfda4eeda8b56fcbd82312c63c0`, four root partitions
73/73/73/70, full hierarchy, `--extract-assembly`, and implementation-source emission. The
`disassembly-regression/1` manifests and `comparison.json` record the tool/configuration identities;
SDK 8 was not mixed into this run.

Baseline and post are exact matches with manifest SHA-256
`db59e07ebaf34ccd582065223b79897b3a75bc64352343497c2f56519cda3533` and zero comparator
differences. The aggregate is 289 roots, 2,745 headers, 83,754 method entries, 60,117 unique
method identities, 4,504 artifact descriptors, 289 reports, 289 source bundles, and 8,116 files.
The comparison treats `orbis-objdump` as canonical disassembly, `orbis-bin` as additive utility
evidence, and compiler/LLVM observations as non-promoting capability or cross-check evidence.
