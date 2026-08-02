# Hexagonal architecture contract

## Status

Accepted and enforced in the primary runtime source tree.

## Source of truth

The contract is derived from `src/ddon_dwarf_reconstructor/` and executed by
`tests/quality/test_architecture.py`. The test suite uses ArchUnitPython
`1.5.0`, pinned in the root `pyproject.toml` and `uv.lock`.

## Dependency policy

| Boundary | May depend on | Must not depend on |
| --- | --- | --- |
| `core/` | Standard library and core modules | `application/`, `domain/`, `generators/`, `infrastructure/` |
| `domain/` | Core contracts, domain models/ports, standard library | Infrastructure modules and `elftools.*` |
| `application/` | Core, domain, and typed ports | Infrastructure modules or concrete external adapters |
| `infrastructure/` | Core/domain ports and models, external libraries | N/A for inward adapter dependencies |
| `main.py` and `infrastructure/composition.py` | Application ports plus concrete adapters | Business-policy reimplementation |

The separate `tools/dwarf_spec_pipeline` project has its own package and
lockfile and is not a runtime dependency.

## Port contract

Ports are narrow use-case conversations. The current outbound conversations are
the class parser, DWARF index, dump lookup, disassembly producer, symbol cache,
and source hash ports. Application and domain signatures use these project-owned
contracts, `core.dwarf` structural protocols, and domain models; they do not
expose concrete pyelftools, zstd, SQLite, subprocess, or durable-catalog types.

`main.py` supplies cache paths and sizes, dump/disassembly factories, and the
durable source-hash adapter. Direct construction is not a separate application
contract; composition-root wiring is the supported path.

## Import details

- New imports are package-relative; `src.` imports are forbidden.
- `TYPE_CHECKING` imports are included in layer rules. Runtime-cycle checking
  ignores type-only edges only because those edges do not execute.
- New code imports the owning policy directly. Duplicate utility modules are
  removal targets, not architecture boundaries.
- Test-only and generated files are outside the scanned `src/` tree.
- ArchUnitPython negated selectors can pass when they match no files. The test
  suite guards the source root and keeps a positive empty-selector control.

## Required checks

```text
uv run pytest tests/quality/test_architecture.py -q
uv run just test-unit
uv run just check
```

The architecture recipe is part of normal `just check`, unit-marked tests, and
CI. The former bespoke AST checker under `tests/support/quality/` is retired.
