# Symbol extraction and assembly acceptance

> Current acceptance record for the identity-based symbol route. The focused and bounded
> observations below are complete. The exhaustive 289-root runs were started against the complete
> local source-bound store, but had not reached atomic publication at the last observation; this
> record deliberately does not invent their counts or completeness status.

## Status and evidence boundary

Status: `in_progress-real-acceptance`.

The implementation and deterministic tests cover one-symbol dependency closure, multi-symbol
union/deduplication, canonical ownership, collision-safe paths, include rewriting, method
signature dependencies, context gating, namespace roots, and IDA-style assembly evidence. The
corrected full header command is currently running externally; the assembly-enabled command will
start only after it reaches a definitive exit/publication status. No result has been promoted into
the retained `generated/` tree.

Header completeness, standalone compiler syntax, PS4 ABI/register/stack/CFI correctness, method
semantics, exact-byte parity, and live PS4 behavior remain separate evidence boundaries. Assembly
is additive evidence and cannot upgrade a header status by itself.

## Inputs and source binding

- ELF: `D:\research\DDON-binaries\IDA9.3\PS4_DDON_02020005_2016_12_21\DDOORBIS.elf`
- ELF SHA-256: `4236f598acc8f15893181455ed195e39dfa4dbfda4eeda8b56fcbd82312c63c0`
- Analytical store: `D:\ddon-dwarf-reconstructor\output\analytical-dwarf\main\store-4236f598acc8f158\manifest.json`
- Doris endpoint: `127.0.0.1:19030`
- Input list: `D:\ddon-dwarf-reconstructor\resources\season2-resources.txt`
- Current input-list SHA-256: `220250a42aa3b9fa64cf3948b6dd1f82b03176dd6fcfa842361320b699eb8437`
- Roots: 289 nonblank entries; first `rAIFSM`, last `rZone`
- Orbis disassembler: `D:\SCE\ORBIS SDKs\12.000\host_tools\bin\orbis-objdump.exe`

The client token `02020005` is inferred from the nearest parent path, producing
`ps4-02020005`. Ambiguous or absent tokens use `ps4-unknown`.

## Corrected exhaustive runs

The current header command publishes to a new external location and does not target the retained
generated bundle:

```text
uv run ddon-dwarf-reconstructor generate D:\research\DDON-binaries\IDA9.3\PS4_DDON_02020005_2016_12_21\DDOORBIS.elf --symbols-file D:\ddon-dwarf-reconstructor\resources\season2-resources.txt --dwarf-store D:\ddon-dwarf-reconstructor\output\analytical-dwarf\main\store-4236f598acc8f158\manifest.json --output C:\Users\morph\AppData\Local\Temp\ddon-symbol-repair-season2-header-v6-20260820

uv run ddon-dwarf-reconstructor generate D:\research\DDON-binaries\IDA9.3\PS4_DDON_02020005_2016_12_21\DDOORBIS.elf --symbols-file D:\ddon-dwarf-reconstructor\resources\season2-resources.txt --dwarf-store D:\ddon-dwarf-reconstructor\output\analytical-dwarf\main\store-4236f598acc8f158\manifest.json --output C:\Users\morph\AppData\Local\Temp\ddon-symbol-repair-season2-assembly-final-20260819 --extract-assembly --orbis-objdump "D:\SCE\ORBIS SDKs\12.000\host_tools\bin\orbis-objdump.exe"
```

The assembly command remains staged for a separate run:

```text
uv run ddon-dwarf-reconstructor generate D:\research\DDON-binaries\IDA9.3\PS4_DDON_02020005_2016_12_21\DDOORBIS.elf --symbols-file D:\ddon-dwarf-reconstructor\resources\season2-resources.txt --dwarf-store D:\ddon-dwarf-reconstructor\output\analytical-dwarf\main\store-4236f598acc8f158\manifest.json --output C:\Users\morph\AppData\Local\Temp\ddon-symbol-repair-season2-assembly-v6-20260820 --extract-assembly --orbis-objdump "D:\SCE\ORBIS SDKs\12.000\host_tools\bin\orbis-objdump.exe"
```

Header retry `v6` started at `2026-08-20T23:06:20+02:00` as a detached process tree rooted at
wrapper PID `19884`, with generator worker PID `37008`. At the `2026-08-20T23:18:57+02:00`
checkpoint it was alive with approximately 1.14 GiB RSS, 49.5 CPU seconds, 157 vtable/type
fallback events, zero `slow_dependency_resolution` records, and no published version directory.
The live Doris process list showed the worker's indexed DIE-row query active on one connection;
this is ordinary source hydration, not the old reference-candidate full scan.

The predecessor header retry `v5` was intentionally stopped at about 5 h 18 m on 2026-08-20.
Its worker had reached approximately 5.19 GiB RSS and 14,392 CPU seconds, with 5,853 slow
dependency records (median 2.05 s, p95 7.08 s, maximum 218.4 s). A 30-second `py-spy` capture
showed `reference_candidates` scanning all loaded DIEs beneath attribute hydration. The process
was terminated before publication; its logs and profile are retained under
`C:\Users\morph\AppData\Local\Temp\ddon-symbol-repair-season2-symbols-acceptance-v5-20260820-profiling`.

The repair removed that single-root identity-preservation regression, reused parsed source targets
by exact CU/DIE identity for union mode, indexed reference candidates, and cached inline reference
attributes. Controlled real-store probes measured:

| Probe | Result |
| --- | --- |
| `rAchievement`, identity-preserving single-root path | 157.5 s, 237 parsed classes, 31 headers |
| `rAchievement`, compatibility single-root path | 58.4 s, 82 parsed classes, 26 headers |
| `rAchievement` + `cUIResource`, union before inline reference cache | 132.0 s |
| Same two-root union after inline reference cache | 97.5 s; byte-identical 31 headers |
| First 10 Season 2 roots, corrected union | 238.6 s, 827 parsed classes, 69 headers |
| `rAbilityAddData`, single-root closure | 43.9 s, 79 canonical classes, 27 headers |
| `rAcquirement`, namespace-root regression probe | 1.46 s, one namespace header |

The optimized 10-root run had no publication nesting beyond the flat version/resource layout, zero
missing generated includes, and one complete `MtObject`, `rTbl2Base`, and `MtDataReader` definition
in the shared headers. Its output contained no `.asm` files because `--extract-assembly` was
intentionally omitted; assembly evidence is a separate acceptance surface.

Historical run observations at `2026-08-19T18:54:39+02:00`:

| Run | Process | Start | Elapsed at sample | Sampled working set | Published version directory |
| --- | ---: | --- | ---: | ---: | --- |
| Header-only | 9752 | 15:54:04 | about 3 h | 3,646,029,824 bytes | not yet present |
| Assembly-enabled | 15516 | 15:40:46 | about 3 h 14 m | 3,754,266,624 bytes | not yet present |

The processes continued emitting `slow_dependency_resolution` records and were not terminated.
Counts, ownership, hashes, root statuses, `.asm` counts, disassembly-request results, and final
`observed`/`partial`/`blocked` statuses must be appended after publication or process exit.

## Environment interruption and retry

The workstation rebooted unexpectedly overnight. Windows Event Log records an unexpected previous
shutdown at `2026-08-20 02:33:02` and the system booted again at `2026-08-20 10:49:31`; both
corrected processes and their terminal sessions were consequently lost before publication. The
two empty attempt directories above are retained and are not interpreted as successful or failed
artifact bundles.

A fresh header-only retry started at `2026-08-20T10:57:43+02:00` with run id
`ad253fe9a03b42849fa98d14c419fa3b` and output root
`C:\Users\morph\AppData\Local\Temp\ddon-symbol-repair-season2-symbols-acceptance-v4-20260820`.
It read all 289 roots and validated the source-bound store and Doris endpoint. At the last
observation it remained active at approximately 660 MB RSS, with no version directory published.
The assembly retry will start only after this header run reaches a definitive exit/publication
status, using a new external output root.

## Focused and bounded observations already completed

- Single-root `rAchievement` external output (`ddon-symbol-repair-achievement-context-v12-20260819`):
  80 classes, 31 headers, 127 diagnostics, no shared headers, no assembly because the flag was
  omitted; generated includes resolved; 31 independent g++ C++20 syntax checks passed; no
  `MtCollection` imports; `MtObject`, `rTbl2Base`, and `MtDataReader` each appeared once.
- Multi-symbol `rAchievement` + `cUIResource` external output
  (`ddon-symbol-repair-multi-final-v3-20260819`): 80 canonical classes, 31 headers, 21 shared
  headers, 5 explicit conflicts, 120 unresolved diagnostics, zero hash failures, all standalone
  g++ C++20 checks passed, no forbidden `symbols`/`implementations`/`methods` directories, and
  one complete `MtDataReader` definition at `rAchievement/MtDataReader.h`.
- The multi-symbol duplicate audit found no repeated complete `MtObject`, `rTbl2Base`, or
  `MtDataReader` definitions. Same-name different-content `MtMatrix`, `MtProperty`, and
  `MtString` definitions were isolated behind deterministic identity-suffixed collision paths and
  retained as explicit conflicts.
- Single-root `rLayout` assembly probe
  (`ddon-symbol-repair-asm-rLayout-v2-20260819`) produced 30 flat `.asm` files, 169 pseudo-call
  comments, 680 semicolon-prefixed source comments, zero bare source rows, and an IDA-style
  metadata prologue. Its Orbis report observed 34 functions and 2,813 instructions; this is
  additive evidence, not ABI or semantic closure.

## Retained historical evidence

The predecessor record `acceptance-season2-corpus-20260819.md` and the existing
`D:\ddon-dwarf-reconstructor\generated\ps4-02020005` artifact are retained unchanged. They
predate the identity-based repair, use the historical manifest contract, and are not evidence for
the current symbol ownership or deduplication contract.
