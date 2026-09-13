# Validation correction decisions

This contract records behavioral decisions for evidence-fidelity findings that cannot be
silently folded into a structural refactoring. It separates accepted artifact-safety changes
from deferred changes to validation status semantics.

## F011 — linker output freshness

**Decision: accepted as an artifact-integrity correction.** A linker invocation writes to a
same-directory temporary output. The final `*.linked.o` path is replaced only after a zero exit
status and a non-empty file result are observed. A non-zero exit, timeout, launch failure, missing
output, or publication failure returns no linked artifact and records a failed, blocked, or
unavailable status with bounded diagnostics. A previous valid final object remains untouched when
a later invocation fails, but it is never returned as evidence for that failed invocation.

This changes only stale-artifact handling and the missing-output success defect. It does not infer
ABI or semantic equivalence, change header output, or promote a linker result into a validation
status by itself. The acceptance tests are
`tests/infrastructure/test_implementation_validation_paths.py::test_linker_failure_does_not_reuse_or_destroy_previous_output`
and `::test_linker_success_without_an_output_is_incomplete`, together with the existing linker
truth table. The implementation is in
`src/ddon_dwarf_reconstructor/infrastructure/implementation_linker.py`.

## F022, F023, and F033 — deferred evidence-status changes

The known control-flow parity, unresolved-call, and missing-source/assembler diagnostic findings
remain deferred. Their current statuses and diagnostics are preserved until each proposal has a
before/after corpus case, an output-parity decision, and an independent acceptance result. This
refactoring does not normalize or reinterpret those observations.

## F037 — durable Stream Load label identity

The load-scoped manifest optimization does not change durable label bytes. Destination table,
producer/configuration identity, repeated requests, and migration of existing append-only labels
require a separate characterization against the target Doris behavior. The deterministic
characterization in `tests/infrastructure/analytical/test_doris_load_identity.py` records the
current contract:

| Case | Current result | Decision |
| --- | --- | --- |
| Same source, family, and relative Parquet path | Repeatable label | Preserve idempotent retry behavior. |
| Changed source identity | Different label | Keep source binding. |
| Changed destination table | Same label today | Treat as a collision risk; do not replay or delete existing labels. |
| Changed producer/configuration | Same label today | Treat as a collision risk; a future versioned label schema must include the identity. |
| Existing label on a repeated request | Doris-controlled idempotency | Preserve the existing receipt until migration evidence exists. |

The production label schema remains unchanged. A future migration requires a target-Doris
duplicate-label probe, a versioned label namespace, and an explicit receipt migration plan; this
slice provides none of those external prerequisites. Existing labels therefore remain authoritative
and no replay or cleanup is attempted.

## F015 — ambiguous method ownership fallback

**Decision: accepted as an evidence-fidelity correction.** Normal implementation discovery
provides the exact class identity in `MethodAssemblyEvidence.owner_class_key`. When that field is
missing in partial or legacy evidence, a display name can identify more than one parsed class.
The publisher now refuses to choose the first insertion-order match: ambiguous exact and
containing-class fallbacks return no class key, place the artifact in `shared`, and omit
unverifiable root ownership. The canonical provenance path and stable method IDs are unchanged.
The regression is covered by
`tests/infrastructure/test_symbol_output.py::test_method_ownership_fails_closed_for_ambiguous_display_name`.
