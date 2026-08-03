# Validate changes

The root `justfile` is the single automation source of truth. The normal correctness loop keeps
deterministic integration tests enabled; shortcuts that exclude integration or real assets are
explicitly named.

## Fast local loop

```powershell
uv run just test-unit
uv run just check
uv run just test
```

`check` includes Ruff, format verification, actionlint, Pyrefly, deptry, structure, architecture,
Markdownlint, Mermaid CLI validation, and the strict documentation build. `test` includes
deterministic integration tests but excludes performance, packaging, and real-asset qualifiers.

For the explicit profiling slice, use the same source of truth:

```powershell
uv run just performance-tools-install
uv run just test-performance-fixtures
uv run just test-performance-real-assets  # only with named local inputs
uv run just performance-profile-index     # only with the explicit local dump default/override
uv run just performance-history
```

The fixture command can gate deterministic budgets. Real-asset runs are report-only and record
cold/warm state, source identity, tool availability, and external manifest paths; a skipped or
unavailable profiler is not replacement evidence.

## Handoff loop

```powershell
uv run just test
uv run just coverage-ci
uv run just audit
uv run just package
uv run just package-smoke
uv run --directory tools/dwarf_spec_pipeline just test
uv run --directory tools/dwarf_spec_pipeline just test-official
uv run --directory tools/dwarf_spec_pipeline just check
```

Run package recipes when distribution behavior changed. Run the nested project from its own
boundary; it has an independent lockfile and dependency contract.

## Explicit environmental evidence

```powershell
uv run just test-real-assets
uv run just test-performance
uv run ddon-dwarf-reconstructor artifacts inspect-elf <PS4-ELF>
```

Real PS4/PS3 assets, MSVC, Orbis, and performance runs are acceptance evidence only when an
explicit local path and the cold/warm state are recorded in the relevant Spec Kit artifact.
Their absence does not invalidate deterministic fixture or integration evidence, but it must not
be hidden behind a green default test command.

## Documentation-only changes

For a docs-only change, run at least:

```powershell
uv run just docs-tools-install
uv run just docs-check
uv run just check
```

Run `docs-tools-install` once after checkout or a documentation-tool lockfile change. `docs-check`
validates every Mermaid fence by rendering it to a temporary SVG and lints the authored site
Markdown with the locked `markdownlint-cli2` configuration before building `site/`. Review the
generated site locally, then remove or leave the ignored build output as convenient. The GitHub
Pages workflow repeats all three checks from the lockfiles.

## Documentation review

Use the [documentation style reference](../reference/documentation-style.md) and the
[authoring how-to](write-documentation.md) before reviewing prose. Confirm that the page has one
Diátaxis intent, an identifiable audience and outcome, source-backed claims, explicit evidence
status, and links to the relevant arc42 compartment or reference contract. Check Mermaid source
with `uv run just docs-diagrams`, Markdown with `uv run just docs-lint`, commands, paths, headings,
and internal links. Delete obsolete duplicate narratives instead of preserving competing
instructions.
