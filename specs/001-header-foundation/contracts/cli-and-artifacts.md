# Contract: CLI and Durable Artifact Operations

## Canonical Entry Points

```text
uv run ddon-dwarf-reconstructor generate <elf> --symbol <symbol>
uv run ddon-dwarf-reconstructor generate <elf> --symbol <symbol> \
  --extract-assembly --emit-implementation-sources --orbis-objdump <path>
uv run ddon-dwarf-reconstructor export-knowledge <elf> --symbol <symbol> --output-dir <dir>
uv run ddon-dwarf-reconstructor artifacts <action> ...
```

The root `main.py` launcher, if retained for native build tooling, is only a
composition entrypoint. The packaged Typer command tree is the supported runtime
surface; the removed argparse syntax and separate artifact executable are not
supported.

## Header Generation Contract

Inputs:

- explicit ELF path;
- one symbol or a symbol file;
- optional full-hierarchy, single-file, exhaustive, dump, and parameter-name options.

Outputs:

- one header string for single-file generation, or a deterministic filename-to-content
  mapping for multi-file generation;
- metadata and diagnostics tied to source identity and DIE/CU evidence;
- completeness state for the root and every structural dependency;
- explicit blocking diagnostics for declaration-only, partial, unresolved, or
  conflicting bases and by-value dependencies;
- no invented method bodies.

Failure behavior:

- an unavailable complete definition is represented by a diagnostic or explicit
  not-found result;
- a blocking completeness or closure diagnostic prevents the output from being
  presented as compilable;
- source/cache mismatch is not silently ignored;
- output ordering, shared-declaration ownership, and filenames are deterministic;
- multi-file output MUST deduplicate shared declarations and include cross-file
  structural dependencies before it can claim aggregate closure.

## Post-header implementation and Orbis contract

`--extract-assembly` is an additive follow-up switch. Header discovery must publish the valid
header bundle and manifest before implementation discovery starts. A profile failure or timeout
cannot roll back that header publication. Known-invalid Orbis options are capability-filtered
before execution. `--emit-implementation-sources` requires `--extract-assembly` and enables the
canonical assembly/object profile; without it the same report remains available without generated
source files. A successful report-only publication retires a stale source bundle for the same root.

For a single `rLayout` root, the durable layout is:

```text
<output>/ps4/header-bundle.manifest.json
<output>/ps4/rLayout.h
<output>/ps4/implementations/0001-rLayout.json
<output>/ps4/implementations/0001-rLayout/
  source-bundle.manifest.json
  methods/<stable-method-id>/<stable-method-id>.raw.asm
  methods/<stable-method-id>/<stable-method-id>.s
  methods/<stable-method-id>/<stable-method-id>.o                 # when accepted
  methods/<stable-method-id>/<stable-method-id>.context.json
```

The JSON index uses implementation-report schema `4.2` and is source-bound to the header bundle
SHA-256, published header-manifest identity, ELF identity, Orbis invocations, tool identity,
raw-output hashes, exact method-range disassembly, decoded instruction provenance, and references.
Instruction-level references are canonical; aggregate method references are derived views. An
assembly artifact is emitted only for one fully matched candidate and one unique Orbis function
with a valid range and decoded bytes. Ambiguous, partial, unsupported, unresolved, deleted,
defaulted, pure-virtual, and unavailable methods stay in the index without synthesized C++
declarations or `extern` statements.

`source-bundle.manifest.json` uses schema `3.1` and contains only the artifact profile, root,
report/header identities, aggregate bundle digest, file count, and publication status. Its
`report_path` is relative to the manifest directory and points to the canonical sibling report.
Per-method descriptors in the report carry kind, role, content type, byte length, producer,
relative path, and SHA-256. The default profile emits bounded original Orbis text as `.raw.asm`,
exact-byte compiler input as `.s`, an SDK-produced `.o` only after acceptance, and an
`implementation-context/1.0` `.context.json` packet. `.raw.asm` is evidence only and is never
passed to `orbis-as`; the context references it rather than duplicating its text. No reference
JSON, unstructured notes, empty files, or `.cpp` files are generated. C++ translation is a later
agentic workflow.

Use the separate read-only command below to validate target objects and the remaining evidence
dimensions in an external directory:

```text
uv run ddon-dwarf-reconstructor artifacts validate-implementation <elf> \
  --implementation-report <implementation-report.json> \
  --dwarf-store <complete-store-manifest.json> \
  --output-dir <external-validation-dir> --original-addresses
```

The command requires an explicit address policy, binds its report to the source/report hashes,
SDK definition identity, relocation evaluator version, and NID database identity, and retains
independent `observed`, `partial`, `blocked`, `not_observed`, `unavailable`, and `failed` statuses
for relocation, NID, ABI/CFI, instruction safety, compiler acceptance, and static parity. Live
PS4 execution remains a separate `not_observed` dimension. Schema `4.2` adds the deterministic
DWARF target manifest, scope hash, retained ELF function candidates, and match reasons. The
optional `--orbis-objdump` comparison is required before CFG/external-edge parity can become
observed; `--orbis-ld` records an optional relocatable link result.

The Orbis report/cache schema is `2.4` and its key includes the consumed profile: symbol flags,
standard relocation flags, resolved disassembly flags, and optional LLVM identities/triples. The
known-invalid `-t -T` and `-R` profiles are not invoked, and the full `--dwarf=info` profile is
not part of the Doris-backed implementation path. The parser identity is `orbis-objdump-text-v7`
and the SCE metadata parser is `orbis-sce-metadata-v3`; profile metadata also validates the exact
command, flags, tool identity, and stdout/stderr hashes before reuse. Profile stdout/stderr and
metadata are written for profiles that run. The in-repository SCE metadata reader retains complete 24-byte
RELA records in a parser-bound JSONL cache and projects only method-relevant entries into the
report. Empty, partial, and malformed evidence remains explicit; unsupported profiles are
documented rather than retried as runtime diagnostics.

The three authorities are fixed by contract: Orbis binutils owns PS4 instruction decoding and
demangling; optional LLVM owns additive generic/target-aware structural cross-check evidence; and
the SCE reader owns PS4 dynamic-tag/relocation-table decoding without applying relocations or
creating external declarations. `--llvm-readobj <path>` uses:

```text
--elf-output-style=JSON --file-header --program-headers --sections --dynamic-table
--relocations --dyn-relocations
```

For `generate`, `--llvm-objdump <path>` requires `--extract-assembly` and uses one independently
cached slice per eligible Orbis function:

```text
--triple=x86_64-scei-ps4 -d -l -C --symbolize-operands
--start-address=<start> --stop-address=<stop> <elf>
```

`--llvm-target-triple` defaults to `x86_64-scei-ps4`; the exact requested/effective triple,
capability probe, range, cache identity, hashes, and comparison summary are retained. LLVM raw
output remains in the external cache and never changes Orbis eligibility. `llvm-readobj` has no
triple interface and is `not_applicable` for target selection. `llvm-tli-checker` is a separate
SDK-library diagnostic and is not used in ELF extraction. The report also records the typed,
source-hashed SDK-definition identity. The official SDK source defines `PT_SCE_DYNLIBDATA`,
`PT_SCE_PROCPARAM`, `PT_SCE_COMMENT`, and `PT_SCE_LIBVERSION`, plus standard `PT_GNU_RELRO`; it
does not define `PT_SCE_RELRO`.

## Compiler Validation Contract

MSVC validation produces one record per standalone translation unit and one separate
record for the aggregate translation unit. Each record MUST include:

- compiler executable and version;
- language standard and complete flags;
- translation-unit name and generated-header inputs;
- process exit code;
- captured stdout and stderr, or an explicit unavailable marker;
- expected object/output status;
- classified warnings and errors, including an explicit C4201 classification.

The aggregate result MUST NOT be synthesized from standalone results. A nonzero
aggregate exit code remains a failed aggregate check even when every standalone probe
passes. Missing captured stderr means a suspected cause, such as repeated shared
declarations, is an inferred hypothesis and MUST NOT be recorded as a confirmed
compiler diagnostic such as C2011.

Validation reports MUST distinguish at least:

- missing structural closure;
- invalid C++ rendering or declarator syntax;
- duplicate declarations in an aggregate or multi-file bundle;
- unavailable external or IDA evidence;
- accepted or unresolved compiler warnings such as C4201.

## Artifact CLI Contract

### `inspect`

```text
uv run ddon-dwarf-reconstructor artifacts inspect \
  --elf <path> \
  --dwarf-dump <path> \
  --dump-index <path>
```

Returns JSON with source-catalog status and, when a dump is supplied, a `dump_index`
object containing:

- `path`;
- `exists`;
- `status`: `missing`, `ready`, `stale`, `invalid`, or `unavailable`;
- metadata when the sidecar is readable.

`inspect` MUST NOT build a missing index. Repeated `--symbol` options and
`--symbols-file` are mutually exclusive at the generation boundary.

### `repair-dump-index`

Repairs current-schema metadata or builds a missing/stale index. It MUST preserve a
previous valid sidecar until the replacement has been fully committed and published.

### `rebuild-dump-index`

Forces one complete streaming scan and atomically publishes a replacement.

### `purge-dump-index`

Deletes only the resolved sidecar when the caller supplies the exact path through
`--confirm-index-path`. A wrong confirmation returns a nonzero status and leaves the
file untouched.

### `repair-symbol-cache`

Restores a selected symbol cache as an explicit replacement rather than merging
unknown source mappings into the current cache.

## Sidecar schema policy

The current sidecar schema is `1.2`, produced by `ddon-dwarf-zstd-index`, with a
configuration digest recorded in metadata. A sidecar with an older schema is a
rebuild input, not a runtime contract; the current reader MUST validate the source
and rebuild explicitly when the schema does not match.
