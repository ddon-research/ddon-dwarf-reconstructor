# Data Model: ABI-Oriented Header Foundation

## Evidence Source

Represents an immutable input or independently produced evidence report.

- `source_kind`: ELF, compressed DWARF dump, Orbis report, fixture, or authority record.
- `resolved_path`: local path used for the current operation; not the stable identity.
- `sha256`: strong content identity when available.
- `size`: source byte size.
- `boundary_sha256`: first/last bounded-region fingerprint for warm validation.
- `producer`: parser or external tool that produced the evidence.
- `producer_version`: producer contract version.
- `configuration_sha256`: output-affecting parser/tool configuration identity.

Validation rules:

- A reusable artifact MUST retain source identity and producer metadata.
- A path or modification time MUST NOT be the only identity.
- A source replacement MUST invalidate dependent offsets and declarations.

## Recovered Type

Represents one DWARF-backed type definition or declaration.

- `qualified_name`: namespace and containing-type-qualified name.
- `unqualified_name`: original `DW_AT_name` when present.
- `aggregate_kind`: class, struct, union, enum, typedef, array, or other DWARF kind.
- `die_offset`: authoritative DIE offset.
- `cu_offset`: containing compilation-unit offset.
- `byte_size`: recovered object size when present.
- `alignment`: recovered alignment when present.
- `declaration_file` and `declaration_line`: source location evidence.
- `completeness`: complete, declaration-only, partial, unresolved, or conflicting.
- `diagnostics`: explicit limitations and selection decisions.
- `bases`: ordered inheritance records.
- `members`: ordered data-member records.
- `methods`: ordered subprogram records.
- `nested_types`: enums, structs, unions, and nested aggregates, each retaining
  containing scope.
- `template_parameters`: recoverable type/value parameter records.
- `containing_type`: qualified containing aggregate for nested classes and enums.
- `nested_definition_status`: complete, forward-declared, unresolved, or conflicting.

Invariants:

- `die_offset` and `cu_offset` remain numeric evidence, not display-only strings.
- A by-value member or base requires a complete referenced type or a diagnostic.
- A pointer/reference-only dependency may be forward-declared when legal C++ permits it.
- A nested template argument retains its containing scope and cannot be rendered as a
  qualified name before the containing declaration exists.

Completeness is a propagated state, not only a property of the selected root DIE:

- `complete`: the definition has the required structural evidence for its use.
- `declaration-only`: a declaration exists but provides no complete layout.
- `partial`: some structural or signature evidence is present but required facts are
  missing.
- `unresolved`: the referenced DIE or dependency could not be located.
- `conflicting`: candidate definitions disagree and selection cannot be justified.

A declaration-only, partial, unresolved, or conflicting base or by-value dependency
creates a blocking validation diagnostic. Pointer/reference-only dependencies may
remain forward-declarable when the rendered C++ use permits it.

## Type Reference

Represents a structured type chain instead of a reparsed display string.

- `terminal_die_offset`: final referenced type DIE when resolvable.
- `qualifiers`: const, volatile, restrict, and address-space evidence.
- `indirection`: pointer, lvalue reference, rvalue reference, array, function, or
  pointer-to-member layers.
- `array_dimensions`: ordered bounds or unresolved expressions.
- `display_name`: deterministic rendered form, never the only stored representation.
- `resolution_status`: resolved, forward-declarable, unresolved, or conflicting.

## Header Bundle

Represents one generated header or a deterministic set of files.

- `target_name`: requested root type.
- `source_identity`: evidence source identity used to generate the bundle.
- `configuration_identity`: renderer and closure configuration.
- `files`: collision-safe relative filenames and content hashes.
- `dependency_order`: stable complete-definition order.
- `diagnostics`: unresolved types, conflicts, unsupported syntax, and compiler limits.
- `standalone_validation`: per-header translation-unit results.
- `aggregate_validation`: the separate multi-header translation-unit result; it cannot
  be inferred from standalone results.
- `generated_at`: operational timestamp; not part of content identity.

## Artifact Index

Represents the durable lookup sidecar.

- `schema_version`.
- `producer` and `producer_version`.
- `config_sha256`.
- `source_sha256`, `source_size`, and `source_boundary_sha256`.
- class definition rows: name, CU offset, DIE offset, nested-type counts, size, score.
- method implementation rows: declaration DIE offset to implementation DIE offset.

State transitions:

1. Missing: no sidecar exists.
2. Building: a temporary sidecar is being populated from one streaming pass.
3. Ready: metadata and tables validate against the source.
4. Stale: source or output-affecting identity differs.
5. Invalid: database is corrupt or missing required tables.
6. Published: a validated replacement atomically replaces a stale sidecar.

## Validation Diagnostic

Represents a visible limitation or disagreement.

- `code`: stable machine-readable diagnostic code.
- `severity`: info, warning, error, or incomplete.
- `entity_id`: affected type, member, method, or artifact.
- `evidence_ids`: contributing DIE, CU, dump, or assembly references.
- `category`: completeness, missing-closure, invalid-rendering, duplicate-declaration,
  unavailable-evidence, compiler-warning, or conflicting-evidence.
- `message`: concise human-readable explanation.
- `blocks_compilation`: whether generated output cannot be validated as C++.

Diagnostics are part of deterministic output and must be ordered stably.

## Compiler Validation Result

Represents one auditable compiler invocation. The aggregate result is a separate
record from each standalone translation-unit result.

- `translation_unit`: source/probe identity, including `compile_tutorial.cpp` when used.
- `compiler`: executable identity and version.
- `language_standard`: selected C++ standard.
- `flags`: complete compiler flag list.
- `exit_code`: process exit code, preserved even when nonzero.
- `stdout` and `stderr`: captured compiler streams, or an explicit unavailable status.
- `object_status`: whether the expected object/output was produced.
- `diagnostics`: parsed warning/error classifications, including C4201.
- `scope`: `standalone` or `aggregate`.

An aggregate failure MUST remain visible when all standalone records pass. A proposed
root cause such as duplicate declarations is an inferred diagnostic until captured
compiler output confirms it.

## External Evidence Availability

An evidence source also records availability independently for declarations, layout
facts, assembly instructions, vtable slots, calling conventions, and decompiler
method bodies. A pseudo-header can support declaration comparison but cannot satisfy
a behavioral or method-body validation criterion. Missing evidence is a first-class
availability diagnostic rather than an inferred agreement.
