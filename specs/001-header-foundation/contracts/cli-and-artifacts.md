# Contract: CLI and Durable Artifact Operations

## Canonical Entry Points

```text
uv run ddon-dwarf-reconstructor <elf> --generate <symbol>
uv run ddon-dwarf-artifacts <action> ...
```

The root `main.py` launcher may remain as a compatibility shim, but it must produce
behavior equivalent to the package entry point.

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
uv run ddon-dwarf-artifacts inspect \
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

`inspect` MUST NOT build a missing index.

### `repair-dump-index`

Repairs compatible metadata or builds a missing/stale index. It MUST preserve a
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

## Sidecar Compatibility

The current sidecar schema is `1.2`, produced by `ddon-dwarf-zstd-index`, with a
configuration digest recorded in metadata. A compatible `1.1` sidecar may be enriched
in place without rescanning when its indexed tables and known source identity match.
