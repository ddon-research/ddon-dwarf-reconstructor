# Validate changes

> **Archived Python project:** This page describes the frozen Python snapshot.
> Development has moved to an unpublished Rust rewrite. See [archive status](../reference/project-status.md).

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

For a cross-module refactoring, retain the active Spec Kit feature's source-bound working-state
receipt with the command results. The current architecture feature records a 590-file receipt at
`output/refactoring-evidence/021/1b10b75e751c97b1/implemented-findings-working-state.json`; its
identity changes when an inventoried production, test, or effective configuration file changes.
The receipt is an evidence identity, not a replacement for generated-output comparison.

For the explicit profiling slice, use the same source of truth:

```powershell
uv run just performance-tools-install
uv run just test-performance-fixtures
uv run just test-performance-real-assets  # only with named local inputs
uv run just performance-profile-index     # only with the explicit local dump default/override
uv run just performance-runtime-compare   # CPython/Nuitka/free-threaded real-asset comparison
uv run just performance-history
```

The fixture command can gate deterministic budgets. Real-asset runs are report-only and record
cold/warm state, source identity, tool availability, and external manifest paths; a skipped or
unavailable profiler is not replacement evidence.

Nuitka builds are also explicit environmental evidence. `native-build` uses `python -m nuitka`,
MSVC, onefile mode, and an external output directory. Free-threaded Python must use a separate
project venv; a bare base interpreter can report a misleading missing-project failure. Nuitka and
Scalene free-threaded blockers remain recorded rather than added to the normal correctness loop,
and pyinstrument is not no-GIL evidence because its native extension enables the GIL on import.

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

The coverage gate rejects required groups with no executable statements. When a module moves,
update the selectors in `tests/support/quality/check_coverage.py`; an empty group is a failed
check, not 100% coverage. Publication helpers, symbol publication, bounded tool execution, and
analytical session ownership are included in the corresponding high-risk groups.
The `cpp_reconstruction` group covers the moved instruction and control-flow services and
requires the same 80% line and 70% branch coverage as the other high-risk groups.

Source-bound parser caches and tool-process evidence are part of the deterministic checks. The
`TypeChainTraverser` cache is created per `ClassParser` session, and failure-path tests verify
that a drained subprocess cannot be reported as successful evidence. Analytical load tests also
verify that one validated manifest identity is reused for all labels in a load invocation; they
do not replace live Doris publication or duplicate-label acceptance.

The architecture quality tests scan inner-layer call expressions for legacy unbounded process APIs
(`os.system`, `os.popen`, and `subprocess.call`/`check_call`/`check_output`) in addition to import
direction rules. The test includes a deliberate violation fixture so an empty selector or a
never-matching AST rule cannot pass silently.

The same architecture suite checks workflow action provenance. External GitHub Action references
must use a full commit SHA and a human-readable release comment; repository-local action paths are
valid. A passing local check proves the checked-in files satisfy that convention, not that remote
repository settings are enabled. Keep remote settings and Dependabot evidence in the feature
record rather than inferring them from YAML.

Implementation-tool validation uses the shared bounded runner. Version, assembler, linker,
objdump, readelf, and ABI-probe calls share finite timeout metadata and bounded stdout/stderr
capture. A timeout, stream-drain failure, or truncated stream is incomplete evidence and must
remain visible in the result diagnostics. Executable identity observations may be reused only
inside one toolchain run/profile; do not add a process-global tool cache when changing a caller.

DWARF search budgets and Doris timeout/wait configuration reject NaN and infinite values at
construction, including values loaded from the environment. Use finite durations; the existing
zero value for `DDON_DORIS_ANALYZE_WAIT_SECONDS` remains valid and disables waiting.

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

With the recovery of the local Doris serving backend on September 9, 2026, full-corpus header
generation, assembly/object parity, and MSVC compiler acceptance are unblocked. Verification proceeds
through the hierarchical canary progression (`MtObject` -> `rLayout` -> `rAIFSM`) culminating in the
unified 289 Season 2 batch run. The deterministic gates above remain fast `Verified` evidence for
every slice before executing real-asset acceptance.

## Documentation-only changes

For a docs-only change, run at least:

```powershell
uv run just docs-tools-install
uv run just docs-api-check
uv run just docs-check
uv run just check
```

Run `docs-tools-install` once after checkout or a documentation-tool lockfile change. Run
`docs-api` when source modules are added, removed, or moved; `docs-api-check` then fails on stale,
missing, duplicate, or unexpectedly grouped generated pages. `docs-check` repeats that check,
validates every Mermaid fence by rendering it to a temporary SVG, lints the authored site Markdown
with the locked `markdownlint-cli2` configuration, and builds `site/` strictly. Review the generated
site locally, then remove or leave the ignored build output as convenient. The GitHub Pages workflow
repeats the same locked checks.

## Documentation review

Use the [documentation style reference](../reference/documentation-style.md) and the
[authoring how-to](write-documentation.md) before reviewing prose. Confirm that the page has one
Diátaxis intent, an identifiable audience and outcome, source-backed claims, explicit evidence
status, and links to the relevant arc42 compartment or reference contract. Check Mermaid source
with `uv run just docs-diagrams`, Markdown with `uv run just docs-lint`, commands, paths, headings,
and internal links. Delete obsolete duplicate narratives instead of preserving competing
instructions.
