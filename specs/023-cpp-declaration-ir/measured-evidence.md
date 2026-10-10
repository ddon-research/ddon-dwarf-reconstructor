# Measured evidence: Declaration IR

This record serves reviewers deciding whether the planned IR and compiler adapter have been
implemented and validated. The package is a specification; implementation has not started.

## Input Evidence

The September 20 review and [Feature 022 evidence](../022-cpp-compilation-repair/measured-evidence.md)
identify useful structured type/scope work, semantic defects, retained full/probe compiler reports,
and a hypothetical language representation limit. They justify this research direction, not
adoption of a new dependency or acceptance of any migration.

Clang 22.1.8 was observed locally and used for small C++17 syntax probes. No normalized AST adapter,
IR round trip, LibTooling build, libclang compatibility matrix, or whole-corpus compiler benchmark
was produced. Primary-source research supports the candidate comparison in [research](research.md).

## Required Evidence Ledger

| Dimension | State | Owning tasks |
| --- | --- | --- |
| Feature 022 repair or source-bound handoff | not_observed | T001 and Feature 022 T020/T019 |
| Common-fixture tool comparison and adoption decision | not_observed | T001,T002 |
| Immutable declarations and migrated families | not_observed | T003-T008 |
| Optional compiler port/adapter and failure behavior | not_observed | T009-T012 |
| Synthetic differential/property semantics | not_observed | T013,T014 |
| Superseded policy removal | not_observed | T015 |
| 289-root compiler/semantic/determinism acceptance | not_observed | T016 |
| Generation and validation resource measurements | not_observed | T017 |
| Final repository quality/coverage/audit | not_observed | T018 |
| New PS4 ABI/layout evidence | not_observed | Independent target-authoritative validation |

Each future entry must identify source and producer fingerprints, tool/profile versions, exact
command, timestamps using system-derived timezone, process/cache state, retained external paths
and hashes, outcome, limitations, and next action. No generated game headers or SDK files belong
in this directory. Blocker handoffs reference Feature 022's structured record and remain open
until the corresponding semantics and acceptance gates are resolved.

## Specification-Package Validation

The package passed explicit Markdownlint and local link/task checks. The shared site passed
`docs-check`; the existing unit suite passed 1,278 tests. Root `check` stopped at two pre-existing
source-formatting failures. See [Feature 022's delivery record](../022-cpp-compilation-repair/measured-evidence.md#specification-package-validation-on-september-20)
for exact boundaries. No IR implementation or compiler adapter was added by this documentation
delivery, and none of the implementation acceptance dimensions above is closed.
