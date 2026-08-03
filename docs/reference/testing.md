# Testing and evidence tiers

Root tests have exactly one scope marker (`unit`, `integration`, or `acceptance`) and at least one
purpose marker (`functional`, `regression`, or `non_functional`). Collection enforcement rejects
ambiguous or missing classifications. `performance`, `slow`, `real_asset`, `packaging`, and
`quality` are explicit qualifiers with additional constraints.

## Default selection

```powershell
uv run just test
uv run just coverage-ci
```

The default correctness expression includes deterministic integration and excludes performance,
packaging, and real-asset tests. `test-without-integration` is an iteration shortcut only. Use
the named recipes for regression, non-functional, acceptance, real-asset, and performance slices.

## What each tier proves

| Tier | Proves | Does not prove |
| --- | --- | --- |
| Unit | isolated parser, model, policy, or adapter behavior | full source integration |
| Deterministic integration | multiple project components and stable bundle contracts | proprietary tool behavior |
| Acceptance | user-visible CLI, packaging, or selected external workflow | every real corpus path |
| Real asset | explicitly named ELF/dump/compiler/tool result | fixture portability or repeatability without the asset |
| Performance | measured time/resource behavior with recorded cold/warm state | semantic correctness by itself |

The knowledge exporter integration path must remain runnable without proprietary ELF inputs. Real
PS4/PS3 inputs are environmental evidence and are never silently substituted for deterministic
tests.

## Nested project

```powershell
uv run --directory tools/dwarf_spec_pipeline just test
uv run --directory tools/dwarf_spec_pipeline just test-official
uv run --directory tools/dwarf_spec_pipeline just check
```

The nested project mirrors the marker vocabulary but has its own lockfile and source boundary.
