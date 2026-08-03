# DDON DWARF Reconstructor contributor guidance

This project extracts deterministic evidence from very large PS4 ELF/DWARF inputs. Performance is
the first constraint: avoid repeated ELF hashing, repeated full-DIE scans, whole-dump loads, and
unbounded in-memory intermediates. Preserve stable output ordering and source offsets.

## Development

- Use regular CPython 3.14.6 and install the complete development environment with
  `uv sync --python 3.14.6`.
- Install Node.js 24.14.1 and the locked documentation validators with `uv run just
  docs-tools-install` after a fresh checkout or a change to `tools/documentation/package-lock.json`.
- Install actionlint v1.7.12 with the platform package manager and ensure it is on `PATH`; the
  root `uv run just check` recipe runs it for every local quality loop.
- Use package-relative imports; do not import the package through the repository's `src` directory.
- Run fast tests with `uv run just test-unit` and the locked quality gate with `uv run just check`.
- Use `uv run ddon-dwarf-reconstructor` as the canonical unified Typer entry point. Generation uses
  `generate`, knowledge export uses `export-knowledge`, and durable maintenance is grouped under
  `artifacts`. Other launchers are implementation details, not separate behavior contracts.
- Real ELF tests are opt-in and must use explicit local paths. Never commit game binaries, dump
  files, generated headers, runtime caches, or credentials.
- The inputs for an identified DDON build are immutable. Retain deterministic SQLite indexes,
  symbol/header caches, and exports locally so fresh-process warm reruns stay fast; untracked and
  rebuildable does not mean routinely disposable.
- Key durable artifacts by source identity plus producer/schema/configuration identity, validate
  before reuse, and publish atomically. Routine cleanup must preserve them; make purge, repair, or
  rebuild narrowly targeted and explicit.
- `SourceIdentityCatalog` is the shared source-binding implementation. A warm identity may reuse a
  verified metadata key when metadata indicates the same filesystem object. The key uses size,
  mtime, device, and inode so an unchanged file can be relocated without a second full hash.
  Retain ctime as a mutation signal and reuse ctime drift only when the recorded path disappeared
  and a new path has the same stable object metadata. Explicit `verify=True` always rehashes the
  complete source; do not create boundary-sampling or path-only identity schemes.
- `SearchResult` is the contract for bounded targeted lookup. Preserve status and candidate
  provenance; partial results are never complete evidence and must not be consumed as complete.
- `ElfDwarfSession` owns the opened ELF/DWARF graph and one-time PS4 normalization. Generated
  headers go through `AtomicHeaderPublisher`, which writes a manifest and rolls back failed bundles.
- External inspection is an explicit artifact workflow: use `artifacts list-tool-profiles`,
  `probe-tool`, and `export-tool-evidence` for bounded one-time exports. Matching Orbis tools are
  authoritative for PS4 ABI/SCE semantics; LLVM, GNU, elfutils, libdwarf, pyelftools, LIEF, and
  OpenOrbis outputs are additive cross-checks until PS4 behavior is validated. `elfldr` is loader
  research only and must not be executed by the offline ingestion path.
- The standard non-proprietary container baseline is
  `tools/binary_toolchain/compose.yaml`. Mount explicit inputs read-only, publish outputs outside
  source control, and never copy Sony SDKs or SELF credentials into the image.
- Opt-in profiling uses the canonical `performance` command group and `just` recipes. Use
  `performance doctor` before selecting tools, the deterministic fixture tier before real assets,
  and `performance history compare/export` for the tracked SQLite/static-history contract. The
  process runner records CPU, RSS/VMS, process I/O, bounded samples, and source identity in an
  isolated child. Raw Scalene, cProfile, pyinstrument, py-spy, tracemalloc, pyperf, stdout, stderr,
  and sample files remain in the OS-local performance artifact directory. Profiling is never
  enabled in normal generation; missing tools/assets are explicit unavailable or blocked evidence.

## Local acceptance artifact

- The PS4 `02020005` compressed LLVM DWARF dump is available at
  `D:\research\DDON-binaries\IDA9.3\PS4_DDON_02020005_2016_12_21\DDOORBIS.elf.llvmdwarfdump.zst`.
- It is about 1.09 GB compressed and more than 30 GB expanded. Validate compressed-dump changes
  against this artifact instead of assuming that only fixtures are available.
- The primary development machine has 64 GB RAM and a Ryzen 7800X3D. A resource-heavy explicit
  bootstrap is acceptable when it produces a persistent, source-bound index and makes subsequent
  lookups fast. Do not impose that bootstrap cost on every invocation.

## Change discipline

Preserve unrelated edits. Add focused tests for DIE traversal and evidence fidelity. Cache entries
must be fingerprinted to their inputs and written atomically. Any optimization must preserve
qualified names, inheritance, field offsets, sizes, source locations, DIE offsets, and deterministic
ordering.

## Maintainability and architecture

- Treat the following limits as maintainability guardrails for every non-generated Python file
  under `src/` and `tests/`: 600 physical lines per module, 500 lines per class (including its
  docstrings and internal documentation), 75 lines per function or method, and McCabe complexity
  of 10. Do not split a cohesive, functionally busy class solely to satisfy a line budget; split
  behavior when responsibilities, dependencies, or complexity justify it.
- Keep the dependency direction explicit: domain code may depend on domain models, ports, and the
  standard library; application code coordinates use cases through ports; infrastructure owns
  `pyelftools`, SQLite, zstd, Orbis/process integration, and filesystem adapters. Only composition
  roots construct concrete infrastructure adapters.
- Prefer typed internal contracts such as `GenerationRequest`, `HeaderBundle`,
  `DefinitionCandidate`, and type/declarator models. Breaking changes are allowed: update all
  in-repository callers, tests, and contracts together. Old import and method shapes are not
  design constraints.
- Keep one canonical implementation for definition selection, source identity, primitive and
  excluded-type classification, method evidence, special-header rendering, and array/declarator
  parsing. Do not reimplement policy in alternate generators or adapters.
- Use explicit `is not None` checks for offsets and other optional evidence; offset `0` is valid.
  Convert expected failures into specific exceptions or structured diagnostics rather than
  swallowing them with broad `except` clauses.
- New imports must be package-relative. Do not import the package through the repository's `src`
  directory, and do not make domain code aware of launchers or infrastructure details.

### Observability and exception policy

- Keep domain and application code on the standard-library logger boundary exposed by
  `core.observability`; infrastructure owns the structlog `ProcessorFormatter` configuration.
  Do not import structlog, Rich, or OpenTelemetry from domain code.
- Prefer `log_event` with stable snake_case event names and bounded fields. Bind `run_id`, command,
  source path/identity, symbol, stage, and optional `trace_id`/`span_id` at context boundaries.
  Do not log ELF/DWARF bytes, complete headers, every DIE, credentials, or unbounded subprocess
  output. Use debug for hot-loop detail, info for stage boundaries, warning for incomplete or
  recoverable evidence, and error only when an operation fails.
- Use `log_exception` or `exc_info=error` at the smallest useful boundary and preserve exception
  chaining with `raise ... from error`. The JSONL file must retain nested traceback frames; the
  stderr renderer is for human diagnosis. Do not replace an exception with `str(error)` alone.
- `LoggerSetup` must preserve foreign root handlers, emit JSONL to the configured log directory,
  and keep application diagnostics on stderr so artifact commands can reserve stdout for JSON.
  New observability behavior requires a focused test for fields, callsite data, and chained errors.

## Test and regression discipline

- Mirror the production package layout in `tests/`; put shared typed fixtures and DIE builders in
  `tests/support/`. Split tests by behavior when a test module or class approaches the structure
  limits.
- Use Hypothesis for pure type, declarator, array, and parser invariants. Use `pytest-regressions`
  only for small deterministic diagnostics, ordering records, and structured metadata; generated
  headers are validated with exact byte comparisons and SHA-256 manifests.
- Exercise incomplete, conflicting, duplicate, unavailable, cyclic, and timeout evidence paths,
  including offset `0`, malformed or stale cache artifacts, interrupted atomic writes, lock
  behavior, and warm lookup reuse.
- Maintain at least 80% total line coverage. Parsing, generation, orchestration, and artifact
  modules each require at least 80% line coverage and 70% branch coverage; keep the explicit
  failure-mode branches tested rather than excluding them from measurement.
- Every generation change must preserve qualified names, inheritance, field offsets, sizes, source
  locations, DIE/CU provenance, deterministic ordering, cache formats, and source identity. Validate
  the canonical entry point and each intentional output mode in fresh and warm-cache processes.
- Keep real-asset manifests and generated headers outside source control. Commit only deterministic
  manifests or small structured expectations that describe those external baselines.

### Test taxonomy and pyramid

- Every collected root test has exactly one scope marker: `unit`, `integration`, or `acceptance`;
  and at least one purpose marker: `functional`, `regression`, or `non_functional`. The collection
  hook in `tests/conftest.py` rejects missing or ambiguous classifications under strict markers.
- `performance`, `slow`, `real_asset`, `packaging`, and `quality` are explicit qualifiers. A
  performance or quality test must also be `non_functional`; a real-asset test must be integration
  or acceptance; a packaging test must be acceptance.
- Required deterministic integration tests are part of `uv run just test`, `coverage`, and
  `coverage-ci`. `uv run just test-without-integration` is an exceptional iteration shortcut, not
  a handoff or merge gate. Use `test-regression`, `test-non-functional`, `test-acceptance`,
  `test-real-assets`, and `test-performance` for explicit evidence slices.
- The performance slices are `test-performance-fixtures` for deterministic budgets and
  `test-performance-real-assets` for named local environmental evidence. Use
  `performance-tools-install`, `performance-profile`, `performance-profile-index`, and
  `performance-history` rather than
  introducing a second shell benchmark wrapper. Real-asset history is report-only and thresholds
  are never auto-learned from noisy runs.
- The knowledge exporter integration path must continue to run without proprietary ELF inputs;
  real PS4/PS3 inputs remain explicitly qualified environmental acceptance evidence.
- Update the Zensical source pages under `docs/`, `docs/knowledge-base/testing/`, and the active
  Spec Kit feature when the taxonomy, test loop, test evidence, or external prerequisites change.

### GitHub Actions and supply-chain policy

- `.github/instructions/github-actions.instructions.md` is the workflow-specific Copilot adapter;
  `AGENTS.md` remains the repository-wide source of truth. Keep workflow changes synchronized with
  `docs/how-to/validate-changes.md`, `docs/explanation/architecture/deployment.md`, the active
  Spec Kit feature, and the testing knowledge base.
- GitHub Actions must mirror the local `just` contract: Code Quality installs the locked
  documentation validators, runs `just check` (including actionlint, Markdownlint, and Mermaid
  rendering), package smoke, and blocking `just audit`; correctness runs taxonomy collection and
  `just coverage-ci`;
  the nested workflow runs its own `just ci` and Compose configuration check. Deterministic
  integration remains in the default correctness selection; real assets and performance remain
  explicit.
- Pin every external `uses:` reference, including first-party and third-party action dependencies,
  to a full commit SHA with a human-readable version comment. Local composite action paths are
  repository source and must be reviewed with the workflow diff. Dependabot owns update discovery;
  verify the release tag and SHA before accepting an update. Do not use `@main`, `@latest`, or
  mutable major-version tags.
- Workflows default to `contents: read`, use credential-free shallow checkouts, cache only through
  the project lockfiles, set timeouts, expose manual dispatch where useful, and cancel superseded
  branch/PR runs. Do not add `pull_request_target` when the workflow checks out or executes
  contributor code.
- Additional write permissions are exceptional: CodeQL may upload `security-events`, and the
  same-repository test-result publisher may write `checks`. Fork pull requests must retain artifact
  evidence without receiving a privileged token. Never log secrets or upload proprietary inputs.
- The public-repository free-plan boundary permits CodeQL, secret scanning, dependency graph, and
  dependency review. Do not make correctness depend on Codecov, paid GitHub Code Security, hosted
  proprietary runners, cloud credentials, or external commercial scanners. Record GitHub Settings
  gaps such as branch protection, secret scanning, or Dependabot security updates as explicit
  remote follow-up actions rather than pretending a checkout edit enabled them.
- For workflow/Dependabot audits, capture `gh auth status`, open PRs, proposal diffs/checks, failed
  run logs, current action refs, and live security settings before editing. Run `uv run just
  actionlint` after workflow changes; the root `check` recipe includes it and hosted quality
  installs the pinned v1.7.12 binary with a checksum before running `check`. Then run the complete
  local and nested validation loop.

## Required validation

After each refactoring slice, run the smallest relevant tests plus the complete fast gate:

```text
uv run just test-unit
uv run just check
uv run just test
```

`uv run just check` includes Markdownlint, Mermaid CLI rendering, and the strict Zensical build.
Use `uv run just docs-serve` for a local preview and keep Mermaid diagrams in Markdown source
rather than generated images. Run `uv run just docs-tools-install` once before the first local
check on a fresh checkout.

Before handoff, also run `uv run just test`, `uv run just coverage-ci`, and `uv run just audit`.
For distribution changes, also run `uv run just package` and `uv run just package-smoke`.
Use the matching just recipes so structure, architecture, typing, lint,
dependency, and duplicate/dead-code diagnostics remain part of routine development.
Ruff, Pyrefly, and deptry are authoritative for linting, formatting, production typing, and
dependency hygiene; Prospector remains focused on duplicate, dead-code, import, complexity, and
maintainability diagnostics and is a blocking CI gate. Run real PS4 and performance checks only
with explicit local paths and record cold/warm state, timing, and manifest identity in the relevant
Spec Kit artifact. The nested `tools/dwarf_spec_pipeline` project has its own uv lockfile and
mirrors the marker vocabulary; run its `just test`, `just test-official`, and `just check` from
that project boundary as applicable.
For nested dependency-update PRs, also run `uv lock --directory tools/dwarf_spec_pipeline --check`
and verify live Dependabot alerts after the dependency graph refresh; do not dismiss an actionable
security advisory when a patched lock entry is available.

## Spec-driven workflow

- Spec Kit 0.15.1 is initialized for Copilot skills mode under `.specify/` and
  `.github/skills/speckit-*/`.
- Project principles live in `.specify/memory/constitution.md`; feature intent and
  implementation artifacts live under `specs/<feature>/`.
- `zensical.toml` and `docs/` are the published documentation source. The site follows Diátaxis
  navigation, uses arc42 for architecture, and keeps Mermaid/UML diagrams as code. Architecture
  uses C4 context/container/component views when each level adds information, with the arc42
  section-8 crosscutting concepts page as the home for recurring policies. Specs remain the roadmap
  and are indexed from `docs/roadmap/index.md` rather than copied into site prose.
- For cross-module behavior changes, use the feature sequence
  `/speckit-specify`, `/speckit-clarify`, `/speckit-plan`, `/speckit-tasks`,
  `/speckit-analyze`, implementation, and `/speckit-converge` as applicable.
- Keep ELF inputs, expanded dumps, SQLite sidecars, generated headers, caches, and
  logs outside Spec Kit feature directories and source control.
- Every task must name exact source/test paths and a validation tier; unresolved
  evidence and deferred compiler prerequisites belong in the feature artifacts.

## Documentation governance

- This file is the durable repository instruction source for Codex; path-specific Copilot
  instructions supplement it. The Markdown adapter is
  `.github/instructions/documentation.instructions.md`, and the reusable writer workflow is
  `.github/skills/documentation-writer/SKILL.md`.
- The authoritative writing contract is
  `docs/reference/documentation-style.md`: classify every authored page with Diátaxis, use the
  applicable arc42 compartments for architecture explanations, keep Mermaid/UML diagrams as code,
  use C4 for progressive architecture abstraction, and label implementation status, authority,
  uncertainty, and deferred work.
- Start documentation with the reader's goal, audience, scope, prerequisites, and evidence
  boundary. Use active, precise, source-backed language. Keep tutorials, how-to guides, reference,
  explanations, and research notes distinct; link between them rather than mixing purposes.
- For current behavior, inspect source and tests; for intended behavior, cite the active spec; for
  research, preserve the source and authority. Remove obsolete duplicate prose instead of creating
  a second contract. Use `uv run just docs-check` and then `uv run just check` for site changes.
- Keep knowledge-graph infrastructure deferred until the explicit `KG-001` task defines the
  versioned loader, deterministic query fixtures, provenance rules, and acceptance evidence.

## Goal-oriented research loop

- For multi-turn correctness work, create a thread-scoped goal whose objective names the outcome,
  evidence surface, preservation constraints, scope boundary, next iteration action, and blocked
  condition. The goal is a workflow aid, not a replacement for these repository instructions.
- For GitHub Actions or Dependabot correctness work, establish remote evidence before changing
  code: run gh auth status, inventory open PRs with gh pr list, inspect each proposal with gh pr
  diff, collect gh pr checks, and read failing job output with gh run view <run-id> --log-failed.
  Treat action/dependency-update checks that pass as proposal evidence, not as a substitute for
  the required correctness job.
- Start DWARF investigations with `artifacts inspect-elf`, `artifacts inspect-dwarf-dump`, and the
  standalone specification `dwarf-spec-pipeline audit` command. For toolchain work, probe local
  `--help`/`--version` surfaces first, then run only named profiles and retain their manifests.
  Record confirmed, approximate, blocked, and remaining-uncertainty findings separately.
- After each parser or evidence slice, run the focused tests, `uv run just check`, and the required
  correctness loop before advancing. Complete the goal only when the named evidence surface passes;
  a time or token budget is never completion evidence.
