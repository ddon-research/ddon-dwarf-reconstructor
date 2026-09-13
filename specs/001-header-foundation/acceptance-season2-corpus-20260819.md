# Historical pre-repair Season 2 extraction

> Retained historical evidence. This record predates the identity-based symbol extraction
> repair and does not describe the current `symbols.manifest.json` contract or current header
> ownership semantics.

## Status and evidence boundary

Status: `historical-observed-partial`.

The complete 289-root source-bound route completed under the predecessor publication contract and
published one atomic version directory. Its ownership and deduplication claims are historical
only; the current repair must be evaluated with a new external output. The command intentionally
omitted `--extract-assembly`, so assembly availability is `not_observed` for this record. This
record does not promote ABI, register/stack/CFI safety, semantic parity, or live PS4 behavior.

## Inputs and command

- ELF: `D:\research\DDON-binaries\IDA9.3\PS4_DDON_02020005_2016_12_21\DDOORBIS.elf`
- ELF SHA-256: `4236f598acc8f15893181455ed195e39dfa4dbfda4eeda8b56fcbd82312c63c0`
- Analytical store manifest: `output\analytical-dwarf\main\store-4236f598acc8f158\manifest.json`
- Input list: `resources\season2-resources.txt`
- Input-list SHA-256: `ec13b918d58723c45b5a6defb78956c1019f9aabad0067572e4538eaefabbdae`
- Doris endpoint: `127.0.0.1:19030`
- Command shape:

  ```text
  uv run ddon-dwarf-reconstructor generate <elf> --dwarf-store <manifest> \
    --symbols-file resources/season2-resources.txt --output generated
  ```

The client token `02020005` was inferred from the nearest parent path, producing
`generated/ps4-02020005`. The source-bound manifest records the same inference source and input
list hash.

## Observed result

| Measure | Result |
| --- | ---: |
| Requested roots | 289 |
| Completed root statuses | 289 `success` |
| Union classes traversed | 2,863 |
| Published headers | 1,244 |
| Shared headers | 296 |
| Assembly files in this run | 0 (`not_observed`) |
| Nested `symbols`/`implementations`/`methods` directories | 0 |
| Manifest schema | `corpus-artifacts/1` |
| Header bundle SHA-256 | `19bb51f679244ffe5002171dd00afccb7b065f792eb1954e7e3ee51736670896` |

The exhaustive traversal and render completed in approximately 66 minutes. PowerShell process
samples observed a peak working set of approximately 3.2 GiB on the 64 GiB host; the worker stayed
responsive throughout. No staging directory remained after the atomic commit.

`MtDataReader` resolved once by qualified identity `MtDataReader|3229|101762`, with owner
`shared` and output `shared/MtDataReader.h`. `rAchievement/rTbl2.h` includes that shared complete
definition. The manifest retains 17,065 diagnostics, including 17,030 explicit unresolved or
unreachable records and 6 duplicate-identity conflict records; these are not hidden by the
successful root statuses.

## Validation disposition

- `observed`: one union traversal, atomic flat publication, source/list binding, file hashes,
  deterministic ownership, root completion, and `MtDataReader` dependency closure.
- `observed`: synthetic IDA-style `.asm` prologue, pseudo-symbol/call comments, semicolon-prefixed
  source references, and unchanged exact-byte `.s` path through the focused tests.
- `not_observed`: real-corpus assembly extraction for this run, because `--extract-assembly` was
  not supplied.
- `not_observed`: ABI/semantic equivalence and live PS4 execution; header generation does not
  substitute for those gates.

The durable predecessor artifact is outside source control at
`D:\ddon-dwarf-reconstructor\generated\ps4-02020005\` and is retained for historical inspection.
