# Research: external binary inspection toolchains

## Confirmed local observations

- Orbis 8.0 host tools are available under the explicit SDK path and identify the PS4 target as
  `elf64-x86-64-freebsd`; Orbis `readelf` exposes ELF/program/section/symbol/relocation/DWARF
  switches and SCE program types.
- MSYS2 LLVM tools report version 22.1.8. `llvm-readelf --elf-output-style=JSON` successfully
  produced machine-readable file-header, program-header, and section metadata for the local PS4
  ELF. Unknown SCE program types remain numeric/unknown rather than becoming false standard names.
- MSYS2 GNU Binutils reports version 2.46.1 and accepts the ELF for generic header/symbol
  comparison. Its target naming does not preserve the Orbis FreeBSD target identity.
- libdwarf `dwarfdump -h` exposes producer printing and integrity checks, including `--check-all`.
- The managed Python environment has `elftools`; LIEF is not installed. pyelftools remains the
  structured in-process parser through `ElfDwarfSession`; LIEF is reference-only until PS4
  custom-segment/type behavior is tested.
- OpenOrbis `readoelf` is a useful reference source for Orbis ELF interpretation. `elfldr` is a
  payload/loader research source and is outside the offline evidence boundary.

## Adoption decisions

| Decision | Reason |
| --- | --- |
| Adopt Orbis header/symbol profiles | Preserve SCE/PS4 ABI authority from the matching SDK |
| Adopt LLVM JSON/DWARF summary profiles | High-value machine-readable additive exports |
| Adopt GNU/elfutils/libdwarf profiles | Independent cross-check and integrity diagnostics |
| Keep pyelftools in-process | Existing session owns handles, normalization, and typed traversal |
| Keep LIEF/OpenOrbis reference-only | Avoid unsupported promotion of generic/custom ABI behavior |
| Exclude elfldr execution | Loader behavior is not offline inspection evidence |

## External references

- LLVM Command Guide: https://llvm.org/docs/CommandGuide/index.html
- GNU Binutils: https://www.gnu.org/software/binutils/
- libdwarf documentation: https://www.prevanders.net/libdwarfdoc/
- pyelftools: https://github.com/eliben/pyelftools
- LIEF: https://github.com/lief-project/LIEF
- OpenOrbis repositories: https://github.com/orgs/OpenOrbis/repositories
- elfldr reference: https://github.com/ps4-payload-dev/elfldr
- PS4 SELF background: https://www.psdevwiki.com/ps4/SELF_-_SPRX

## Uncertainty and follow-up

- The real PS4 ELF export pass completed with schema `1.1`. Orbis header evidence is keyed by
  `696180705efd088147a1f83d5a4884fee9fa64bb36843610276d5fef63d42d70` and its output SHA-256 is
  `2b24b9eef4be186a46bd71d270f4b5ef5b0129652a581a9f5140defc5c4d3f98`; LLVM JSON evidence is
  keyed by `1a0e0536308627088e93dfffff43d1a4446b16384f92ff052bc413c3005a7182` and its output
  SHA-256 is `e04a920eb1cafd384709eb641c4da4ca47d0b978054875eea2f8d87dbffadf5a`; libdwarf
  summary evidence is keyed by `fb52d4d01590587bc835de31ad7175714d363390a85215775115b7dff3f9b58c`.
  Warm reruns reused those content keys. Raw files remain outside the repository.
- The normal libdwarf profile is `--check-summary`; the full `--check-all` profile is explicitly
  capped at 64 MiB and fails closed. A diagnostic run demonstrated why: it produced about 4.33 GB
  of raw output, which is retained only in ignored local output and is not a normal ingestion path.
- Docker Compose configuration, image build, generic version smoke, and direct container LLVM JSON
  probing passed. The container preserved `FreeBSD` OS/ABI and Sony type `0xFE10`; its generic
  labels are still reference evidence rather than PS4 ABI authority.
- Root unit/check/test/coverage/audit/package/package-smoke and nested test/test-official/check
  passed. The nested official test remains an explicit skip because its official prerequisite is
  unavailable in the current environment.
- LIEF and OpenOrbis should be evaluated on the same PS4 fixture only in a separate comparison
  feature; no generic output currently promotes a layout or ABI fact.
