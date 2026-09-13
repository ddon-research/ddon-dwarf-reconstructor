# Season 2 resource-class header and assembly validation

## Status and evidence boundary

This is the latest real-asset acceptance record for the 289 nonblank roots in
`resources/season2-resources.txt`. It is `observed-partial`: root/header publication and clean
assembly bundles are complete, while ABI, register/stack/CFI safety, static semantic parity, and
live behavioral equivalence remain independent evidence dimensions.

Production inputs were the source-bound Doris analytical store, ELF metadata, and PS4 SDK 8.0
tools. The runtime did not open Parquet or JSONL analytical projections. IDA was used only by the
separate post-generation completeness audit and could not modify targets, names, addresses,
caches, compiler inputs, or statuses.

Source identity:

- ELF SHA-256: `4236f598acc8f15893181455ed195e39dfa4dbfda4eeda8b56fcbd82312c63c0`;
- Doris manifest: `output/analytical-dwarf/main/store-4236f598acc8f158/manifest.json`;
- Doris manifest SHA-256: `bbe354bf3f838c8a1da6da501b9829a1bedf533f4834f0a4710dcbb574886078`;
- Doris schema: `1.1`; address policy: explicit ELF link-time/original addresses;
- Orbis tools: SDK 8.000 `orbis-objdump` and `orbis-as`.

The machine-readable aggregate audit is retained outside the repository at
`C:\Users\morph\AppData\Local\Temp\ddon-season2-validation-20260816\season2-validation-audit.json`.

## Supersession table

These boundaries are intentionally separate and must not be added together:

| Record | Headers/methods | Interpretation |
| --- | ---: | --- |
| Historical full boundary | 2,745 headers | Prior pre-refactor full run; retained historical comparison |
| Boundary-refactor attempts | 1,653 headers at most | Blocked/partial attempts; no complete acceptance claim |
| Current Season 2 run | 2,760 headers | Current source-bound publication and independent MSVC closure |
| Current clean assembly handoff | 1,150 method bundles | Bounded clean `.raw.asm`/`.s`/`.o`/context artifacts; semantic dimensions remain partial |
| Historical complete validator | 1,150 method requests | Dated pre-T087 per-dimension report; ABI, compiler transformation, parity, and live behavior remain open |
| Current bounded T087 validator | 1,037 method requests | Corrected post-effects/parity pilot; failed/partial and not target-object equivalent |

The current run supersedes the 2,745-header count for status reporting but does not erase the
historical or blocked evidence.

## Complete run

The source list was executed in four bounded batches. Every batch exited successfully with zero
generation failures:

| Batch | Roots | Header manifests | Implementation reports |
| --- | ---: | ---: | ---: |
| 001 | 73 | 73 | 73 |
| 002 | 73 | 73 | 73 |
| 003 | 73 | 73 | 73 |
| 004 | 70 | 70 | 70 |
| **Total** | **289** | **289** | **289** |

### Headers

- 2,760 per-root header file entries and 10,093,364 published header bytes were checked;
- all 2,760 recorded sizes and SHA-256 values matched actual files;
- all 289 header manifests recorded `failed=0`;
- no root was missing, duplicated, or extra.
- The independent MSVC closure report
  `C:\Users\morph\AppData\Local\Temp\ddon-season2-validation-20260816\msvc-season2-full\msvc-header-validation.json`
  passed 2,760/2,760 translation units across 289 bundles, with zero failures and zero
  timeouts. It recorded only classified warnings: `C4201` (125) and `C4309` (1). This proves
  host declaration/closure acceptance, not PS4 ABI behavior.

### Assembly bundles

The implementation reports contain 84,553 method rows, 9,429 retained function candidates, and
55,575 decoded instructions. Their independent method statuses are:

- 1,350 matched;
- 758 ambiguous;
- 6,463 unsupported;
- 75,982 not observed.

There are 138 roots with at least one matched method, 150 roots with methods but no match, and one
root (`rAcquirement`) with no method rows. The latter are association/scope evidence gaps, not
proof that the methods do not exist.

The clean handoff contains 1,150 of each artifact kind: `.raw.asm`, canonical `.s`, accepted
Orbis `.o`, and `implementation-context/1.0` `.context.json`. All 3,450 context descriptors
matched their paths, sizes, and hashes. Raw text matched the report’s normalized
`raw_disassembly` for 1,150/1,150 methods, and the `.text` section matched the `.s` byte stream for
1,150/1,150 objects. There are zero `.cpp`, empty placeholder, reference, or unstructured
diagnostic artifacts.

The first concurrent pass exposed a source-cache defect: JSON serialization changed SDK identity
tuples into lists, so valid SCE metadata caches were reparsed and one `rLoadingParam` publication
encountered a Windows cache-file contention diagnostic. The fix compares canonical JSON values and
binds disassembly report keys to `SCE_METADATA_PARSER_VERSION`. The affected root was rerun alone
with clean evidence: SCE metadata `observed`, 172,943 relocation entries, and zero diagnostics.
The original contaminated root is not used as final evidence.

## Independent completeness and validation audits

The isolated IDA audit is
`C:\Users\morph\AppData\Local\Temp\ddon-season2-validation-20260816\ida-audit-season2\implementation-coverage-audit-8316eff47d43abb9.json`.
It is schema `1.0`, `observed`, and `cross-validation-only`: 84,553 production method rows were
compared with 108,412 IDA named bodies; it recorded 21,459 exact name matches, 3,516 ambiguous
matches, 63,094 methods without a named IDA body, and 20,363 IDA bodies without generated
assembly. These observations are possible scope/association diagnostics requiring DWARF/ELF
algorithm review; they do not repair or promote production evidence.

The pre-batching Doris-backed static validator was run against the 1,150 emitted methods with
`--original-addresses`, the complete Doris manifest, and explicit SDK tools. At the time of this
record it remained CPU-active without an atomic report after more than one hour. No timeout was
configured or recorded. This baseline exposes a serving-model gap: method validation currently
performs per-method Doris DIE/location/CFI work and rescans the complete relocation/NID tuples,
rather than using the intended bounded batch context projection. The run is therefore retained as
an algorithmic-performance diagnostic, not promoted as static evidence. It remains separate from object
acceptance: assembling `.s` and matching `.text` is not ABI or semantic equivalence. The incomplete
temporary validator directory was sent to the Windows recycle bin; only this concise aggregate
status is retained.

## Bounded-validator implementation follow-up (2026-08-16)

The next implementation slice addressed the algorithmic gap exposed above. The validator now
prefetches method, formal-parameter, object-pointer target, location, and CFI evidence through
bounded Doris batches, installs a read-only in-memory context view, and builds relocation and NID
indexes once per run. The query projects only the typed columns needed for this evidence. Runtime
generation and validation still do not open Parquet or JSONL.

The batching change passed its focused analytical/implementation validation tests and initial unit
gate (`864 passed, 7 deselected`). The retained `rLayout` pilot then published an atomic schema-4.0
report in approximately 28.6 seconds for 1,037 methods. The complete Season 2 validator published
an atomic schema-4.0 report in approximately 85.8 seconds for 1,150 methods at
`C:\Users\morph\AppData\Local\Temp\ddon-implementation-validation-season2-20260816-batched\implementation-validation-4236f598acc8f158.json`
(SHA-256 `97a83535c366f2b8d7e6015fda7f2a9177fda45d1b0621402ba79e77552ac71b`). Its Doris context
summary was `3` batches, `1,150` requests, `7,554` DIE rows, `30,050` attribute rows, `7,179`
references, `4,662` locations, and `90,969` frame rows. Relocation and opaque NID evidence were
observed for all methods; CFI was observed for all methods; effects were `711 observed`, `397
partial`, and `42 failed`; ABI was partial for all methods; compiler acceptance was not observed;
and static parity remained `1,108 partial` and `42 failed`. The report remains failed by design,
not because Doris or the runner was unavailable. No arbitrary tool timeout was used.

### Context-fidelity follow-up

Inspection of one bounded live Doris request found a serializer gap: the typed location family
returned `expression_json`, while the validation summary looked only for legacy `expression`,
`details`, or `decoded_value` keys. The context builder now decodes that Doris field and carries
the recovered ABI-facts map into the validation context packet. Focused validation tests pass,
and a live one-method Doris probe now reports structured frame-base and parameter expressions.
The full report hash above predates this correction; it remains the batching/status baseline and
is not evidence that the older packet contents contained those cues.

At that intermediate correction point, the repository gates passed with `867` tests and `5`
deselected, coverage at `80.34%` total (`83.9%` lines / `67.3%` branches in the named aggregate
groups), and zero Prospector findings. The later diagnostic-policy slice is recorded below; the
full report hash
above remains the pre-policy batching baseline.

### Diagnostic-policy follow-up

Implementation validation now propagates an optional `--tool-timeout-seconds` value through the
ABI probe, assembler, readelf, objdump, and linker stages. The default is no timeout. Validation
retains tool identity, command, output hashes, and concise statuses; it does not publish raw
stdout/stderr files or per-method diagnostic artifacts. Timeout evidence, when a caller explicitly
configures a limit or an external runner imposes one, contains only tool, stage, elapsed time, and
configured limit. Focused implementation tests passed, `just check` passed, and the current full
gates are `870` unit tests/`7` deselected and `872` correctness tests/`5` deselected, `80.44%`
coverage, zero Prospector findings, and 305 generated
API modules. No documented-invalid SDK profile was re-executed and no broad Season 2 validation
rerun was needed for this policy-only change.

### Bounded T087 gate attempt (2026-08-16)

The bounded `rLayout` validator was rerun after the T086 effects/CFI and parity-contract
changes. The run used the complete source-bound Doris publication through the explicitly mapped
local FE SQL port and wrote only to
`C:\Users\morph\AppData\Local\Temp\ddon-plan-t087-20260816-corrected`. The exact invocation was:

```powershell
$env:DDON_DORIS_SQL_PORT = "19030"
$env:DDON_DORIS_HTTP_URL = "http://127.0.0.1:18030"
$env:DDON_DORIS_STREAM_LOAD_URL = "http://127.0.0.1:18040"
uv run ddon-dwarf-reconstructor artifacts validate-implementation resources/DDOORBIS.elf `
  --implementation-report output/ps4/implementations/0001-rLayout.json `
  --output-dir $env:TEMP/ddon-plan-t087-20260816-corrected `
  --dwarf-store output/analytical-dwarf/main/store-4236f598acc8f158/manifest.json `
  --original-addresses --sdk-root "D:\SCE\ORBIS SDKs\8.000" `
  --tool-timeout-seconds 60
```

The run completed in approximately 36.5 seconds and published schema-`4.0` report
`C:\Users\morph\AppData\Local\Temp\ddon-plan-t087-20260816-corrected\implementation-validation-4236f598acc8f158.json`
with SHA-256
`7900e5ead99a18a44f1e8bfe534fb5aed3a996add6ff9dfb86e33bbb7bdb9fee`. Doris context was
`complete` through three batches for 1,037 method requests (`die=3,337`, `attribute=11,360`,
`reference=2,779`, `location=419`, `frame=72,999` rows). The report remained `failed` by its
fail-closed contract:

| Dimension | Result |
| --- | --- |
| Relocations | 26 observed; 1,011 not observed |
| Opaque NID bindings | 1,037 observed; no community mapping was supplied, so named NID coverage remains unverified |
| ABI/CFI | ABI partial for 1,037; CFI observed where method context was available |
| Instruction effects | 17 observed, 8 partial, 1 failed, 1,011 not observed |
| Orbis clang probes | 8/8 observed; method-specific compiler/object acceptance not observed |
| Static parity | 1 failed, 1,036 partial; no `target-object-equivalent` promotion |
| Live PS4 behavior | `not_observed` |

Because no method satisfied the complete ABI/effect gate, the target-object stage did not invoke
`orbis-as`, `orbis-readelf`, or `orbis-objdump`; their target-acceptance status is therefore
`not_observed`, not passed. The separate tool identity probe retained these exact local binaries:

| Tool | Version identity | SHA-256 |
| --- | --- | --- |
| `orbis-as` | Binutils 2.22 / Orbis 8.00.0.398 `f8fc24e5` | `3363c49f805efe94c88bbd613395dfef7218e7745a4f5ba4a94d11e26f40b43e` |
| `orbis-clang++` | clang 10.0.0 / PS4 clang 8.00.0.403 `e0bf6e60` | `23d6af4dded0fd4c1a44899745581452849cdf7db80380da7c717cb5f8467d09` |
| `orbis-readelf` | Binutils 2.22 / Orbis 8.00.0.398 `f8fc24e5` | `41e0ac9a558ce9fec4aa11f7066465d40ab98ea0216b629dfce854e086eba43` |
| `orbis-objdump` | Binutils 2.22 / Orbis 8.00.0.398 `f8fc24e5` | `682b07bd4a87113c7cf6d9cbec97b57b94a157cc93c6ee2ae24f39ed0f2519e9` |
| `orbis-ld` | Orbis 8.00.0.514 | `e9e9d2f080bbc794c53b4c152f12c003528dc48c1766cc3b4f0f1742c0666d84` |

The corrected bounded run is current validator evidence, not static-equivalence closure. The
earlier attempt using the default FE port `9030` is retained as a blocked environment diagnostic;
the active Compose service publishes SQL on `19030`.

## Community NID evidence follow-up (2026-08-17)

The bounded `rLayout` generation and validation workflow was rerun with the community-derived
`aerolib.csv` mapping. The mapping and provenance manifest remain outside source control at:

```text
C:\Users\morph\AppData\Local\ddon-dwarf-reconstructor\external-evidence\community-nids\aerolib-20260817\aerolib.csv
C:\Users\morph\AppData\Local\ddon-dwarf-reconstructor\external-evidence\community-nids\aerolib-20260817\aerolib.provenance.json
```

The downloaded mapping contains 97,623 lines and 8,925,192 bytes with SHA-256
`b80fd57038f66a222548f07fbf78124237e5f3b3abb8645218fd88895e817a95`. Its pinned source is
`https://github.com/SocraticBliss/ps4_module_loader/blob/657f9d380abfec9097bc4bddbc63551b3cd5e47b/aerolib.csv`;
the provenance also records the PS4 default NID suffix
`518D64A635DED8C1E6B039B1C3E55230`. The provenance manifest SHA-256 is
`43d6d0e635a297dc35fb301bd26db48b67ab71255dfa284e2aed46a3e2410377`.

Generation used the complete Doris manifest and the active FE SQL endpoint `127.0.0.1:19030`.
It published to
`C:\Users\morph\AppData\Local\ddon-dwarf-reconstructor\external-evidence\generation-20260817-rLayout-v2`:

- `rLayout.h`: 82,548 bytes, SHA-256
  `30c8eab2e6c624c0f31013bcefa79c28db5f07983aa931c142019670a623817e`, byte-identical to the
  existing repository output;
- implementation report schema `4.2`, SHA-256
  `01a017bd53b77d2aafee340817787bebf780327b11098de9475e15a357394178`;
- 1,037 method rows, 26 matched implementation candidates, and 2,639 decoded Orbis instructions.

The validator published schema `4.1` to
`C:\Users\morph\AppData\Local\ddon-dwarf-reconstructor\external-evidence\validation-20260817-rLayout-aerolib-v2\implementation-validation-4236f598acc8f158.json`
with SHA-256
`b93e57de17ac3cc80335b9c8011d7e63879d8344ba4a49888a468c7c1e255423`. The NID dimension now
records 1,209 `community_verified` bindings with observed hash and dynamic library/module
context, plus 103 opaque SCE dynamic-identity records. All 1,037 method-level NID statuses are
observed. The validator remains overall `failed`: ABI is partial for all 1,037 methods, effects
are `17 observed`, `8 partial`, `1 failed`, and `1,011 not observed`, and parity is `1 failed`
and `1,036 partial`; compiler transformation and live behavior remain `not_observed`.

The run also corrected NID context decoding after the first report exposed that dynamic-tag
string-table offsets had been compared with multi-character encoded table IDs. The validator now
compares the upper dynamic-tag table IDs; the focused regression covers `#BM#k`. This changes only
NID evidence classification and does not alter header bytes or canonical assembly eligibility.
The full Season 2 validator remains deferred until the bounded representative gate closes all
required dimensions.

The follow-up repository loop passed 877 deterministic tests with 5 deselected, `just check`,
the focused five-test NID slice, and `docs-check`. These repository gates do not promote the
remaining PS4 ABI, semantic, or behavioral dimensions.

## Local Orbis SDK 12 CPU/ABI evidence slice (2026-08-17)

The offline CPU/ABI integration was exercised against the local
`D:\ddon-dwarf-reconstructor\resources\DDOORBIS.elf` (size `800622848`, SHA-256
`4236f598acc8f15893181455ed195e39dfa4dbfda4eeda8b56fcbd82312c63c0`) with the promoted SDK
`12.000` host profile. The observed `orbis-bin` identity was SDK 12.00.0.2, tool SHA-256
`c911af44f77b93fdc96d7ce9def0bba3858fe43dd935a83bdae2cd7a4f8f7763`. All raw exports and probe
files remain under `C:\Users\morph\AppData\Local\Temp\ddon-orbis-sdk12-*`.

| Observation | Result | External manifest/output evidence |
| --- | --- | --- |
| `orbis-bin -dss` | `rLayout::load(MtStream&)` matched exactly at `4504` bytes; 120,239 stack rows parsed | manifest key `c9926958055272864a42495feb7bcb8b9c322a7644c412521443d52d955d2371`; output SHA-256 `acd2e4faabe16bcc727f399ccbc4c6bdc5ad07695450d5fd76ed324587e7a95c` |
| `orbis-bin --dump-dynsym -v` | 650 dynamic-symbol rows parsed | manifest key `db1e48614f487dc4288cc40ddd7391ead7c99c8d5b450e7bc2e04a87d4a26531`; output SHA-256 `d68ed2f46b35032b912102e826bc396162f9a485e433a3f62209ba6e6084770f` |
| `orbis-bin -r` | 28,431,184-byte inline relocation display published successfully | manifest key `5c3c0938efd29f546746e5885ba198c55462aef2d041a3ea664982a5fd537cd6`; output SHA-256 `111b045496914a63b21e11d3b3d2f409c5a39d3e397deea3b5f768209c83b48a` |
| section, memory, and file layout profiles | all three complete and source/tool-bound | keys `e4d93e8a0dfc93b3630f6c2d8ebbd41cc865f516a18d7c1514dfd29d0a1d4e17`, `a23361a3513c09077931872724737e5c673dfe19b07532650068cb6918f8f5c8`, and `4cc17c92583c00180ddc94d96970f34f6c83c96588f13fd90214ad192679576d` |
| compiler ABI matrix | 8/8 SDK 12 probes observed; each retained `-S` assembly, `-c` object, source hash, command, CFI, `.sce_stack_sizes`, `.debug_aranges`, `.text.<symbol>`, `e_flags=0x04000000`, and object metadata | `C:\Users\morph\AppData\Local\Temp\ddon-orbis-sdk12-probes\compiler-probes-1a0530a0a75911a0.json`; compiler SHA-256 `1a0530a0a75911a0817240e157779de1a70caa9e4e6a7d89520c9455bd704510` |
| canonical assembly bytes | SDK 12 `orbis-as` accepted the existing canonical `rLayout::load(MtStream&)` byte-replay source; `.text` size `3205`, SHA-256 `6073fe10213d913f4d845a3d49fcc75c9e076ac96c39e2f7f91506c752f21ba2` | source SHA-256 `82b5b1adb9ed1b3aa162cf353bf2ae3310b85fe7fbf0e41df131e50cde69df7b`; reassembled object SHA-256 `abcf7f29eb277b28ae38ab806cfbdae5fa61b411cd4b1e925d7cfbfe12bb253c` |
| marked `orbis-llvm-mca` sample | one closed region observed with JSON and resource-pressure output; performance-only evidence | input SHA-256 `e63fe2e9da3a7bf2482912656efed127b2c15ba92b93ed0fa6085132c3829dd3`; output SHA-256 `174a15aacb6472c7e66fbd70880761395f010994512af265c7d73721ae2f4db4`; tool SHA-256 `c5e0cb29c4734b63b981b4ac7db3ddf08bf75147a69335279162d4f156523cb3` |

The first inline-relocation attempt used GNU-only `-C -w -F` flags and failed on SDK 12; the
profile was corrected to Orbis `-r` and rerun successfully. This is retained as tool capability
evidence, not hidden as a skip. The SDK 12 contract is host-tool evidence only and does not prove
the ELF's build SDK. Compiler acceptance, `orbis-bin` output, and `llvm-mca` performance modeling
remain separate from method-specific ABI closure, semantic equivalence, and live PS4 behavior.

## Remaining open points

- DWARF-to-Orbis association remains incomplete or ambiguous for the method/root statuses above;
  IDA observations identify possible gaps but are not discovery input.
- The historical 1,150-method validator observed relocation application and opaque NID identity;
  the 2026-08-16 bounded 1,037-method rerun observed opaque NID identity but only 26 relocation
  rows. The 2026-08-17 follow-up supplied a pinned community map and verified the NID hash and
  dynamic table context for 1,209 unique bindings in the same bounded `rLayout` report. This is
  external community evidence, not official authority, and it does not establish full Season 2
  named coverage or ABI/semantic equivalence.
- ABI remains partial for the historical 1,150-method validator and the current 1,037-method pilot.
  CFI coverage is observed where context is available, while register preservation, stack alignment,
  indirect calls, and instruction effects remain independently classified. The historical effects
  counts were `711` observed, `397` partial, and `42` failed; the current pilot counts are in the
  T087 table above.
- Orbis `orbis-as` acceptance is observed for the emitted canonical assembly objects. C++/Orbis
  clang transformation acceptance is not implied, and no C++ files are generated.
- Static semantic parity remains partial/failed and is not `target-object-equivalent`; live PS4
  behavioral equivalence remains `not_observed`.
- The validator’s per-method Doris/relocation work has been replaced by bounded batch queries and
  address-indexed evidence. The full run is now an observed failed report; remaining work is to
  close the individual ABI, effect, compiler, and parity gates, not to increase a timeout.

## Repository gates

The post-run repository gates completed successfully: `test-unit` passed 874 tests with 7
deselected; `check` passed; `test` passed 876 tests with 5 deselected; `coverage-ci` passed at
80.50% total line coverage; `audit` reported zero Prospector messages; and `docs-api`,
`docs-api-check`, and `docs-check` passed. The latter validated 305 API modules in six pages and
17 Mermaid diagrams across 68 Markdown files. These gates validate the implementation and
documentation, not the unavailable PS4 static or live-behavior dimensions.

## SDK 12 validator and final repository gate follow-up (2026-08-17)

The integrated SDK 12 path was then exercised through the canonical
`artifacts validate-implementation` command against the same local ELF, complete analytical
store manifest, six source-bound `orbis-bin` manifests, and the retained 8/8 compiler probe
manifest. It published the external schema-4.3 report at
`C:\Users\morph\AppData\Local\Temp\ddon-orbis-sdk12-validation-20260817\implementation-validation-4236f598acc8f158.json`
with SHA-256
`8403b96403e334c6fb44eef6143b63979e4e828acdc9584805793877c8d7eb79`. The report selected
`orbis-sdk12-llvm18`, observed all six `orbis-bin` profiles, 172,943 relocations, 1,312 NID
bindings, and 8/8 reusable ABI probes across 1,037 methods.

The aggregate status is intentionally `failed`, not normalized to success: method ABI remains
`partial` for all 1,037 methods; method compiler acceptance is `not_observed`; the Doris model
was unavailable (`DorisConnectionError`); and the `rLayout::load` effect/parity case retained
unsupported `vxorps`/`vmovaps`/other listing diagnostics and an incomplete symbolic path. Live
PS4 execution and behavioral equivalence remain `not_observed`. This is expected bounded evidence
from the new workflow and does not weaken the method-specific ABI, static-equivalence, or live
behavior gates.

The final repository loop passed: `test-unit` 889 passed/7 deselected; `check` passed;
`test` and `coverage-ci` 891 passed/5 deselected; total coverage 80.38% with all named
high-risk groups above threshold; `audit` reported zero Prospector messages; and
`docs-api`, `docs-api-check`, and `docs-check` passed for 319 API modules. These repository
gates validate the implementation and documentation, while the external report preserves the
unavailable Doris and method-level PS4 dimensions explicitly.

## SDK 12 bounded static-evidence gate, schema 4.4 (2026-08-17)

After the T086 effect normalization, source-bound ABI closure checks, parity normalization, and
legacy-report migration, the canonical validator was rerun against the same source and complete
analytical publication. The external report is
`C:\Users\morph\AppData\Local\Temp\ddon-orbis-sdk12-t087-20260817-final2\implementation-validation-4236f598acc8f158.json`
with SHA-256
`752FA0CF923DCD303CDCE34EDD5EEEAAB4F7BD8BF95E516C6D0B6C5F85DD2BFE`. It is schema `4.4`,
status `partial`, source-bound to ELF SHA-256
`4236f598acc8f15893181455ed195e39dfa4dbfda4eeda8b56fcbd82312c63c0` and analytical manifest
SHA-256 `bbe354bf3f838c8a1da6da501b9829a1bedf533f4834f0a4710dcbb574886078`.

| Dimension | Observed result | Boundary |
| --- | --- | --- |
| Frozen code-bearing set | 26 methods, 2,639 Orbis instructions | The other 1,011 discovery rows have no complete code range and remain `not_observed`/`not_promoted` |
| SDK 12 host tools | `orbis-sdk12-llvm18`; six `orbis-bin` profiles observed; 172,943 relocations; 1,312 NID rows; 8/8 compiler probes observed | Host-tool identity does not prove the target ELF build SDK or semantic equivalence |
| T086 effects | 26/26 method effect summaries observed, including normalized prefixes/aliases, vector effects, stack/frame transitions, and bounded path joins | Unknown, conflicting, indirect, and exhausted paths remain non-promoting diagnostics |
| ABI | 17 observed, 9 partial | The nine partial rows lack complete source-bound return-type/ABI facts; compiler probes do not substitute for method locations |
| T087 target objects | 26/26 retained method `.s`, `.o`, and linked `.o` artifacts with source/tool/object hashes, SDK `orbis-as`/`orbis-readelf`/`orbis-objdump` evidence, section metadata, and `e_flags` | Canonical byte-replay remains the default; compiler-generated probe metadata is separate capability evidence |
| Stack-size utility evidence | `rLayout::load(MtStream&)` observed at 4,504 bytes in the source-bound SDK 12 `orbis-bin -dss` export | The discovery identity is signatureless `rLayout::load`; the full-signature utility row remains additive evidence |
| Static equivalence | 17 `target_object_equivalent`, 9 `not_promoted` | No `conflicting` or `failed` disposition occurred in the 26-row set; no runtime/behavioral equivalence is claimed |

T086 and T087 implementation/evidence slices are complete for this bounded set. T088 now has an
explicit per-method disposition, but the gate remains observed-partial because nine methods do not
meet the ABI/CFI closure required for promotion. Full Season 2 expansion, header completeness,
MSVC closure, IDA evidence, and live behavioral equivalence remain separate backlog items.
