# Data model: Declaration IR

> **Archived Python project:** This page describes the frozen Python snapshot.
> Development has moved to an unpublished Rust rewrite. See [archive status](../../docs/reference/project-status.md).

This design reference defines proposed internal contracts. Implementation names may be split
into cohesive modules, but the evidence/identity/emission boundaries must remain explicit.

## Observation and Declaration

An immutable `Observation` contains source identity, CU/DIE locator, DWARF kind, recovered facts,
and completeness/conflict status. Optional facts retain unknown separately from false and zero.
Compiler-derived facts have a separate origin and cannot overwrite recovered observations.

A `DeclarationId` identifies a resolved semantic declaration within a source/configuration scope.
It is deterministically derived from canonical scope, kind, template signature/arguments where
applicable, and disambiguating evidence. Raw object addresses, unqualified names, and compiler
node IDs are forbidden identity keys. Multiple observation locators can support one declaration;
unresolved same-name observations remain distinct candidates until compatibility is established.

`Declaration` is a tagged immutable union for aggregates, enums, aliases, template primaries and
specializations, members, and methods. It refers to canonical `TypeReference`/`TypeScope` values,
source observations, lexical owner, access, and evidence status. Declaration and definition are
different events for the same identity. Enum facts and method compatibility follow Feature 022.

Template arguments preserve type/non-type/template kind, typed values where evidenced, exact
identity, and unresolved spelling with provenance where not resolved. Names do not prove parameter
kinds. Base metadata keeps DIE references distinct from actual displacement/virtual/access facts.

## Requirements and Emission

`Requirement` carries consumer/provider IDs, required capability, context, reasons, and evidence.
Reuse the five availability/completeness kinds from Feature 022; retain multiple obligations.

`EmissionPlan` contains ordered events, lexical ownership, file assignments, declarations that
satisfy each requirement, and unschedulable diagnostics. Rendering consumes this plan without
re-parsing type strings. Stable tie-breaking derives from identity and source ordering policy.

`EmissionLedgerEntry` maps declaration/event IDs to relative path, byte span or line/column range,
file hash, source observations, and synthesized-token reasons. Multiple output fragments may
belong to one declaration; forward and complete events must not look like duplicate definitions.

## Compiler Evidence

`CompilerProfile` binds tool executable/version/hash, adapter/schema version, language standard,
target/data model, flags, include paths/environment, and limits. Host MSVC, host Clang, and any
target-authoritative profile are distinct identities.

`CompilerResult` contains input hashes, profile ID, process outcome, bounded diagnostics,
normalized types/declarations/relationships, unsupported fields, resource measurements, and
external raw-output hashes. Outcomes are `passed`, `failed`, `timeout`, `unavailable`,
`unsupported`, or `incomplete`; only `passed` with complete requested coverage can satisfy a gate.

Normalized observations retain qualified identity, declaration kind, ownership, canonical type,
template relationships, source joins, and compiler-synthesized status. Addresses and transient AST
IDs are discarded. A successful compiler exit with truncated extraction is `incomplete`.

## Migration State

A migration record identifies the declaration family, old/new policy paths, source/producer
fingerprints, intentional changes, fixture and corpus evidence, resource costs, and removed
legacy paths. Progress is `specified`, `adapted`, `validated`, `legacy_removed`, then `accepted`.
Acceptance requires all applicable Feature 022 dimensions; no transition is inferred from task age.
