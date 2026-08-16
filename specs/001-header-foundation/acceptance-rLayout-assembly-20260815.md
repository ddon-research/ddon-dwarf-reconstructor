# `rLayout` assembly acceptance evidence (historical snapshot)

Status: `observed-partial`

This record describes the source-bound revalidation run on 2026-08-15. Generated headers,
implementation reports, caches, and reconstruction files remain outside source control. The
corrected bundle was published atomically under the canonical output root below.

This snapshot is retained for provenance only and is superseded by the 2026-08-16 Season 2
acceptance record. Its one-off SDK capability observations are documented centrally and are not
re-executed by the current workflow; current bundles do not emit C++ scaffolds or raw diagnostic
streams.

## Inputs and endpoint evidence

- ELF: `D:\research\DDON-binaries\IDA9.3\PS4_DDON_02020005_2016_12_21\DDOORBIS.elf`
- ELF SHA-256: `4236f598acc8f15893181455ed195e39dfa4dbfda4eeda8b56fcbd82312c63c0`
- Analytical store: `output/analytical-dwarf/main/store-4236f598acc8f158/manifest.json`
- Orbis executable: `D:\SCE\ORBIS SDKs\8.000\host_tools\bin\orbis-objdump.exe`
- Orbis executable SHA-256: `682b07bd4a87113c7cf6d9cbec97b57b94a157cc93c6ee2ae24f39ed0f2519e9`
- LLVM `llvm-readobj.exe` SHA-256: `ee3187d08cb6a5ebeee0db917899edbf7c77ce5e48ebf4b707acbd3a4a96ab`
- LLVM `llvm-objdump.exe` SHA-256: `0e7668489e2b25144643c4876cefb3a11516846970cfe4378abffe7e545274f7`
- Canonical output: `D:\ddon-dwarf-reconstructor\output\ps4`
- Doris FE SQL endpoint: `127.0.0.1:19030`, database `dwarf`, user `root`.

The initial failed invocation used the application default `127.0.0.1:9030` without the local
host-port override. That port was closed, while the Compose FE was running and published as
`19030 -> 9030`; a direct SQL handshake on `19030` reported Doris `5.7.99`, selected database
`dwarf`, and 19 tables. The corrected run set `DDON_DORIS_SQL_HOST=127.0.0.1` and
`DDON_DORIS_SQL_PORT=19030`, completed with exit code `0`, and therefore records Doris as
`observed`, not unavailable.

## Historical pre-correction publisher baseline

The header baseline remained byte-identical through the corrected publication:

- Header: `82,548` bytes; SHA-256
  `30c8eab2e6c624c0f31013bcefa79c28db5f07983aa931c142019670a623817e`.
- Header manifest SHA-256:
  `0e221b82979872bec39351a16f35ebb71338de73bc3c0f144a41fdc57af7037d`.
- Header-bundle digest:
  `dcf9bf17cf083d01fef0fd4c591a152636c9a8d16aa94e283cbbe383c2a9d8b0`.
- The implementation report is schema `3.2`; the canonical bundle contains 1,037 methods and 26
  compact `.cpp` files with no legacy `.s`, `.disassembly.txt`, `.references.json`, or notes.

## Historical pre-correction revalidation result

The corrected run published the header before starting implementation discovery and atomically
published the following canonical implementation bundle:

- Header: `82,548` bytes, unchanged SHA-256
  `30c8eab2e6c624c0f31013bcefa79c28db5f07983aa931c142019670a623817e`.
- Header manifest SHA-256: unchanged
  `0e221b82979872bec39351a16f35ebb71338de73bc3c0f144a41fdc57af7037d`.
- Implementation report schema/status: `3.2` / `partial`; report SHA-256
  `d802093dfa9722cf3b0ae303d8f22d3d14ebe8056f8628ea66ad40afe341794d`.
- Source-bundle manifest schema/SHA-256: `2.0` /
  `e6d5331882c430e07b16754c9ddef9e3d162fd1c418097bdf8b4fb733a94f21c`.
- Source-bundle digest: `b5d9fb26f00ae8507154065917579886ad354848af7383c3b0dbfd47c5035467`;
  `file_count=26`.
- The source-bundle manifest points to the canonical sibling report as
  `../0001-rLayout.json`.
- Methods: `1,037` indexed; `49` unique DWARF implementation matches; `26` unique
  DWARF-to-Orbis associations; `26` generated `.cpp` files; zero legacy sibling artifacts.
- Implementation statuses: `matched=49`, `ambiguous=16`, `not_observed=928`, `unsupported=44`.
  Assembly statuses: `matched=26`, `ambiguous=16`, `not_observed=951`, `unsupported=44`.
- Orbis report artifact key:
  `ba2c670678f1e3f153563f9f55e566ba1e609a47dad49ba1e753818eb24d3aa2`.
- Orbis cache/report identity: schema `2.4`, parser `orbis-objdump-text-v6`, SCE parser
  `orbis-sce-metadata-v3`, SDK definition identity `orbis-sdk6500-n267`.

The generated `.cpp` files include the unique declaring header mapping and contain only the
guarded GNU/Clang scaffold, canonical definition signature, stable method link, and structured
limitations. No untyped `extern` declaration was synthesized.

## Relocation and LLVM evidence

The SCE reader observed two validated 24-byte RELA tables:

- `DT_SCE_RELA`: virtual address `41144`, file offset `39015400`, size `4137696`, entry size
  `24`, count `172404`.
- `DT_SCE_JMPREL`: virtual address `28208`, file offset `39002464`, size `12936`, entry size
  `24`, count `539`.

The complete source/tool/parser-bound JSONL cache contains `172,943` entries. The canonical
implementation report contains only 3 method-relevant entries, all linked to instruction
addresses; the complete cache remains the authority for the other records. This is why an empty
conventional relocation view does not imply that the ELF has no relocation metadata.

Retained Orbis profile outcomes were independently classified as private-header support observed,
standard relocation output empty, and the dynamic-relocation, symbol, and full-DWARF profiles
unavailable in this SDK/tool surface. These capability facts are documented once in the current
tool reference and were not used to widen scope or promote evidence.

The opt-in LLVM target profile used `x86_64-scei-ps4` for
`llvm-objdump --triple=x86_64-scei-ps4 -d -l -C --symbolize-operands`:

- requested/observed slices: `36/36`;
- target instructions: `2,368`;
- Orbis-comparable instructions: `2,364`;
- address/byte matches: `2,364`; mismatches: `4`;
- target summary status: `observed`.

The generic `llvm-readobj` metadata profile remains additive and records unknown numeric SCE
dynamic tags. Its lack of a triple option is recorded as `target_status=not_applicable`; it does
not replace Orbis instruction decoding or the in-repository SCE parser.

## Validation boundary and remaining uncertainty

Header syntax/closure, source-bound DWARF identity, Orbis evidence availability, PS4 instruction
fidelity, and GNU/Clang scaffold syntax are separate evidence categories. This run does not
establish runtime relocation-base application, loader mutation, NID authority, Sony ABI behavior,
register clobbers, stack safety, host acceptance of the Orbis dialect, or semantic equivalence.

The remaining open points are whether a newer Orbis tool exposes useful `-R`/DWARF payloads,
whether optimized/inlined source mappings are precise enough for reconstruction, whether LLVM's
accepted triple models Sony-specific ABI/relocations, whether a PS4 compiler validation
environment becomes available, and whether future agent workflows need derived per-method
context packets. External variables and methods remain evidence only.

## Implementation-generation validator added after this baseline

The publisher baseline above is retained as historical schema `3.2` evidence. The current
read-only `artifacts validate-implementation` workflow publishes schema `4.0` and adds separate
source-bound dimensions for explicit load-image geometry, pure relocation application, opaque or
database-backed NIDs, DWARF parameter/object locations, CFI, conservative instruction effects,
Orbis clang/as/readelf acceptance, and static parity. The canonical C++ output is now a
non-executable evidence stub; canonical `.s`/`.o` artifacts are emitted only in the external
validation directory after target-tool acceptance.

The bounded SDK 8.0 probe matrix accepted the integer, floating-point, aggregate, `this`, hidden-
sret, variadic, virtual, and `noexcept` probe shapes, and the Orbis assembler accepted a raw-byte
method object. Those probe results are compiler/tool evidence, not proof of every discovered
method's ABI. The validator's complete-store input is now a Doris publication pin: it queries the
typed serving families for method DIEs, locations, and CFI and does not read Parquet/JSONL rows.
Live PS4 execution and behavioral equivalence remain `not_observed`/`blocked`.

## Historical pre-correction Doris-backed validator rerun

The complete source-bound validator was rerun after the final Doris model, CFI range predicate,
and fail-closed assembly-gate changes. The run used `DDON_DORIS_SQL_HOST=127.0.0.1`,
`DDON_DORIS_SQL_PORT=19030`, database `dwarf`, the complete manifest above, and the explicit
`--original-addresses` policy. Its external report is
`%TEMP%\ddon-implementation-validation-real-20260815-doris-v6\implementation-validation-4236f598acc8f158.json`
(109,603,543 bytes; SHA-256
`30106120bce1bc883eaf0f29006d6f46c92b37c6653089e4996d17aeeb703b87`); the report is schema
`4.0` and the validation profile is `source-bound-static-doris`.

The report binds analytical evidence to backend `doris`, database `dwarf`, table
`dwarf_records`, serving variant `canonical`, manifest schema `1.1`, manifest SHA-256
`bbe354bf3f838c8a1da6da501b9829a1bedf533f4834f0a4710dcbb574886078`, and registry status
`complete`. It records 1,037 methods, 172,943 relocations, 1,312 opaque NID records, and
eight observed SDK 8.0 ABI probe objects. The per-method dimensions are:

- relocation: `observed=1,037`;
- NID: `observed=1,037` (opaque identities; no unsupported name authority was inferred);
- ABI: `partial=1,037`;
- CFI: `observed=26`, `not_observed=1,011`;
- instruction effects: `observed=14`, `partial=11`, `failed=1`, `not_observed=1,011`;
- compiler/object: `not_observed=1,037`;
- bytes, CFG, external edges, and semantic parity: `not_observed=1,037`.

The overall report is `failed` because the evidence gates remain incomplete. This is an honest
static result, not a Doris availability failure. The validator emitted no method `.s` or `.o`
artifacts; the eight `.o` files retained under `abi-probes/` are the independent ABI probes.
This prevents the previous empty-instruction/placeholder-object path from being treated as
Orbis compiler acceptance or semantic equivalence. The 26 CFI-covered methods were obtained
through Doris range-overlap predicates; no global CFI family was materialized in Python. No
Parquet or JSONL row was read during this validation run; those files remain one-time
producer/load or audit artifacts only.

## Historical pre-correction schema-4.1 generation and IDA audit

The implementation-generation chain was rerun from the complete Doris publication after the
schema-4.1 and target-scope changes. It used the same ELF, manifest, explicit original-address
policy, and Orbis SDK 8.0 tools. The command exited `0` and published the current report at
`output/ps4/implementations/0001-rLayout.json`:

- report SHA-256: `d4fbc1871dc516a8ebd01adf12c5a9078b5f46212ef2c09be24babbcc98cf29d`;
- report schema/status: `4.1` / `partial`;
- methods: `1,037`; DWARF-derived disassembly targets: `28`;
- target-scope policy/hash: `dwarf-range-closure-v1` /
  `ccb1aecc504b4c4a957a437a242cdcd649125e4375daf09f3f8a87e1bc589236`;
- implementation statuses: `matched=49`, `ambiguous=16`, `not_observed=928`, `unsupported=44`;
- assembly statuses: `matched=26`, `ambiguous=16`, `not_observed=928`, `unsupported=67`;
- source artifacts: `26` non-executable guarded C++ evidence scaffolds.

The Orbis profile retained `2,639` instructions across `28` functions. The unavailable profile
classes above remain historical tool limitations; they did not broaden the target scope or promote
a method.

The post-generation IDA audit consumed only that report and
`DDOORBIS.elf.c`, and wrote the external artifact
`%TEMP%\ddon-implementation-validation-real-20260815-doris-v6\ida-audit-current-implementation\implementation-coverage-audit-d4fbc1871dc516a8.json`.
It reports schema `1.0`, status `observed`, authority `cross-validation-only`, and
`production_pipeline_uses_ida=false`:

- report methods: `1,037`;
- IDA named bodies: `108,412`;
- exact method-name matches: `257`;
- ambiguous matches: `49`;
- IDA body without generated assembly: `232` (`214` not observed, `14` unsupported,
  `4` ambiguous rows);
- parser diagnostics: `0`.

The audit uses names only as a completeness signal, so overloaded/duplicate method rows are
retained as possible gaps rather than treated as exact function associations. It did not modify
Doris targets, production reports, ranges, caches, compiler inputs, or statuses. The 232 rows are
therefore follow-up DWARF/ELF diagnostics, not evidence that IDA is authoritative or that a body
is absent from DWARF.

## Canonical assembly correction

The current implementation-generation contract supersedes the pre-correction `.cpp` scaffold
bundle described in the historical sections above. The core generator now emits the assembly
handoff required by the next agentic workflow:

- report: `output/ps4/implementations/0001-rLayout.json`, schema `4.1`, status `partial`;
- report SHA-256: `e73f34ce1f4a1bb0e750f62bf89f055c07c9bd6c670677119a1df8660c7b796f`;
- artifact profile: `canonical-assembly`;
- source-bundle manifest schema/SHA-256: `3.0` /
  `2dd50399aff5cc3f729fb7ce6c20420d871f0bc60c60aee8b542a30dd263c11d`;
- bundle digest: `3e2c56228fac0e9cb62ad4ba8df40cb2bd8c8810fbc8d0eee821acff792d3991`;
- bundle files: `26` `.s` files and `26` SDK-accepted `.o` files (`52` files total);
- methods: `1,037`; DWARF-derived targets: `28`; scope hash unchanged at
  `ccb1aecc504b4c4a957a437a242cdcd649125e4375daf09f3f8a87e1bc589236`;
- matched implementation and assembly associations: `26` each; no `.cpp` files were emitted.

The SDK profile plan was also narrowed to data consumed by the production chain: symbols,
bounded disassembly, and the standard relocation cross-check. The combined `-t -T` symbol form
and `-R` dynamic-relocation option are known SDK 8.0 limitations and are capability-filtered
before execution. The full `--dwarf=info` objdump pass is not needed because Doris is the
source-bound DWARF authority, so the earlier 120-second timeout is retained only as historical
documentation and is not retried. The Orbis objdump default has no arbitrary two-minute timeout;
an explicit caller may provide a timeout for a bounded diagnostic run.

These `.s`/`.o` artifacts prove exact-byte assembly emission and assembler acceptance only. They
do not promote relocation application, method-specific ABI/CFI safety, static semantic parity,
or live behavioral equivalence. C++ translation is intentionally deferred to the agentic
workflow, and live PS4 execution remains `not_observed`.

## Current Doris validator and IDA audit

The corrected static validator was rerun against the current schema-4.1 report after profile
capability filtering and canonical assembly publication. It used the complete Doris registry and
the explicit `--original-addresses` policy. The external report is
`%TEMP%\ddon-implementation-validation-real-20260815-doris-v7\implementation-validation-4236f598acc8f158.json`
(109,697,867 bytes; SHA-256
`06d5ebdbf5acd950d1d155a883d58ce9a9894a49880facd296e3abaee50ed40b`), schema `4.0`, status
`failed`, and binds implementation-report SHA-256
`e73f34ce1f4a1bb0e750f62bf89f055c07c9bd6c670677119a1df8660c7b796f`.

The report records 1,037 methods, 172,943 relocation records, 1,312 opaque NID records, and
eight observed SDK ABI probe objects. Relocation records are `observed=6,137` and
`partial=166,806`; method relocation status is `observed=26`, `not_observed=1,011`. NID records
are `observed=103`, `not_observed=1,209`, while method-level opaque NID identity is retained for
all 1,037 methods. Method-level ABI is `partial=1,037`, CFI is `observed=26` and
`not_observed=1,011`, instruction effects are `observed=14`, `partial=11`, `failed=1`, and
`not_observed=1,011`, and compiler acceptance is `not_observed=1,037`. Static parity is
`partial=25`, `failed=1`, and `not_observed=1,011`. The failed aggregate is therefore the
fail-closed evidence result, not a Doris or tool timeout.

The post-generation IDA audit was rerun independently at
`%TEMP%\ddon-implementation-validation-real-20260815-doris-v7\ida-audit-current-implementation\implementation-coverage-audit-e73f34ce1f4a1bb0.json`
(309,987 bytes; SHA-256
`afffb1826908de56ca18f654c66bfc423e288997f6f805fc8d019a27aa5cc0d4`). It is schema `1.0`,
status `observed`, authority `cross-validation-only`, and records the current implementation
report SHA-256. Counts are 1,037 report methods, 108,412 IDA named bodies, 257 exact name
matches, 49 ambiguous matches, 232 IDA bodies without generated assembly, and 780 named methods
without an IDA body. These observations remain diagnostics for DWARF/ELF association logic and
did not alter Doris targets, production reports, caches, compiler inputs, or statuses.

The normal generation bundle is the separate canonical handoff: 26 exact-byte `.s` files and 26
SDK-accepted `.o` files, with no `.cpp` files. The validator did not emit method objects because
its method-specific safety/parity gates are incomplete; the eight ABI probe objects are retained
as independent compiler evidence only. No Parquet or JSONL row was read during validation.

## Clean bundle contract implemented after this run

The historical counts above describe the schema-4.1 publication and are not rewritten. The
current publisher contract is schema `4.2` for the implementation report and `3.1` for the source
bundle manifest. An eligible method now publishes bounded original Orbis text as
`<stable-id>.raw.asm`, canonical exact-byte assembler input as `<stable-id>.s`, an accepted
`<stable-id>.o` only after `orbis-as` succeeds, and a deterministic
`<stable-id>.context.json` packet using `implementation-context/1.0`. The raw file is evidence
only and is never passed to the assembler; no C++ or empty/reference/diagnostic placeholders are
created. The context is built from the Doris query port and source-bound report/ELF evidence, with
missing ABI, CFI, relocation, NID, compiler, or parity dimensions recorded explicitly.

A fresh real `rLayout` publication under this contract was a separate acceptance action. The
completed T081 result is recorded below. The historical 4.1 counts above remain unchanged and are
not used as evidence for the current bundle.

## Clean 4.2 bundle acceptance — 2026-08-16

The fresh run used the complete source-bound Doris publication and wrote to the external directory
`%TEMP%\ddon-clean-rlayout-20260816\ps4`. It did not read Parquet or JSONL during generation. The
ELF, Doris manifest, and tool paths were:

- ELF: `D:\research\DDON-binaries\IDA9.3\PS4_DDON_02020005_2016_12_21\DDOORBIS.elf`;
- source identity: `4236f598acc8f15893181455ed195e39dfa4dbfda4eeda8b56fcbd82312c63c0`;
- Doris analytical manifest: `output/analytical-dwarf/main/store-4236f598acc8f158/manifest.json`;
- Doris manifest SHA-256: `bbe354bf3f838c8a1da6da501b9829a1bedf533f4834f0a4710dcbb574886078`;
- backend/query policy: `doris` / `read-only-doris`, manifest schema `1.1`;
- Orbis SDK 8.0 tools: `orbis-objdump` and `orbis-as` from the installed host-tools directory.

Generation exited `0` after publishing 24 headers and a partial implementation report. The
implementation report is schema `4.2`, status `partial`, and has SHA-256
`ee1e45d2313654a80b97f3bcc4c1c921adb0351680d3c84cf9b55e6be57353cb`. It contains 1,037 method
rows, 28 DWARF-derived target functions, 2,639 decoded instructions, and 26 matched implementation
and assembly associations. The target scope remains `dwarf-range-closure-v1` with scope hash
`ccb1aecc504b4c4a957a437a242cdcd649125e4375daf09f3f8a87e1bc589236`.

The source-bundle manifest is schema `3.1`, contains 104 files, and has bundle SHA-256
`29138a44cb683642bf51b6547d380fc1de48b2f1007a9fba0e1aea9e99b0a67b`. The 26 eligible methods
each have exactly one `.raw.asm`, `.s`, `.o`, and `.context.json` sibling. The raw files have
26/26 exact normalized-byte matches with the report's `raw_disassembly`; all 104 descriptors
resolve and match their recorded hashes and lengths; and independent ELF inspection found exact
`.text` parity for all 26 `.s`/`.o` pairs. There are zero `.cpp`, empty, reference, notes, or
unstructured diagnostic artifacts. Context packets are schema `implementation-context/1.0`; all
26 have zero packet diagnostics and retain the independent `not_observed` ABI, safety, parity, and
live-behavior statuses.

Only four useful Orbis invocations were retained in the report: symbols, two bounded disassembly
profiles, and the conventional standard-relocation cross-check. Symbols and disassembly were
observed; conventional relocations were empty. The known-invalid `-t/-T` and `-R` combinations and
the obsolete full-DWARF profile were not executed, and no arbitrary timeout diagnostic was created.

The separate Doris-backed validator used the same report and explicit `--original-addresses`
policy. Its external report is
`%TEMP%\ddon-clean-validation-20260816\implementation-validation-4236f598acc8f158.json`,
109,722,351 bytes, SHA-256
`678ec14a65ce3f7ed7df00452baf825c868ef44790ab75761fc4a1483299f9b2`.
It is schema `4.0`, status `failed`, and remains fail-closed: 172,943 relocation records and
1,312 opaque NID records were retained; method relocation status is `observed=26`,
`not_observed=1,011`; NID status is `observed=1,037`; ABI is `partial=1,037`; CFI is
`observed=26`, `not_observed=1,011`; instruction effects are `observed=14`, `partial=11`,
`failed=1`, `not_observed=1,011`; compiler acceptance is `not_observed=1,037`; and static parity
is `partial=25`, `failed=1`, `not_observed=1,011`. The eight accepted ABI probe objects remain
independent probe evidence; they do not promote method-specific compiler or semantic status.

The post-generation IDA audit is isolated at
`%TEMP%\ddon-clean-validation-20260816\ida-audit\implementation-coverage-audit-ee1e45d2313654a8.json`,
SHA-256 `38e5809ffb7d04229c55e0a7142eeb6a180824d023b5a767c1d66dd89bd8c314`. It is schema `1.0`,
status `observed`, authority `cross-validation-only`, and records
`production_pipeline_uses_ida=false`: 1,037 report methods, 108,412 IDA named bodies, 257 exact
name matches, 49 ambiguous matches, 232 IDA bodies without generated assembly, 780 methods without
a named IDA body, and zero audit diagnostics. None of these observations changed Doris targets,
production names/addresses, caches, compiler inputs, or evidence statuses.

Live PS4 execution and behavioral equivalence remain `not_observed`; assembly/object acceptance is
not semantic equivalence.
