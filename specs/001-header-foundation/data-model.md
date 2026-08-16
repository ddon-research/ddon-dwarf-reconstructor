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

## Orbis Implementation Evidence

The post-header report uses implementation-report schema `4.2` and is source-bound to the
generated header bundle SHA-256, published header-manifest SHA-256 when available, the ELF
identity, and the Orbis evidence artifact key. It stores:

- `OrbisReference`: `kind` (`direct_call`, `indirect_call`, `direct_branch`,
  `indirect_branch`, `data`, or `relocation`), target address, resolved name,
  raw operand, relocation text, and resolution status;
- `OrbisToolInvocation`: profile name, exact command and flags, return status,
  observed/empty/unavailable status, stdout/stderr paths and SHA-256 values,
  tool identity, duration, and bounded diagnostics;
- `OrbisDynamicTag`: numeric SCE tag, optional known name, and raw value;
- `OrbisSceSegment`: relevant SCE program-header type and file/virtual geometry used for bounded
  address-to-file conversion;
- `OrbisRelocationTable`: `DT_SCE_RELA` or `DT_SCE_JMPREL` descriptor, virtual/file range, entry
  size, count, and `observed`/`partial`/`malformed`/`not_observed` status;
- `OrbisRelocationEntry`: stable table-local ID, raw `offset`, `info`, signed `addend`, symbol
  index, relocation code/name, raw bytes, optional symbol name, resolution status, and optional
  instruction addresses. Complete entries are stored in the source/tool/parser-bound JSONL cache;
  the implementation report contains only method-relevant entries and links;
- `OrbisStructuralCrossCheck`: optional LLVM `llvm-readobj` profile identity, status, output hash,
  unknown numeric SCE tags, and bounded diagnostics. It is additive and never outranks Orbis
  instruction evidence or the SCE reader;
- `OrbisTargetedDisassemblyCrossCheck`: optional per-method LLVM `llvm-objdump` projection with
  requested/effective triple, capability status, slice counts, cache identities, address/byte
  comparison totals, and bounded diagnostics. Complete slice output is cache-owned and is not
  duplicated in this report;
- SDK-definition identity: typed package/version, target triple, BFD target, and source file
  hashes for the reproduced Orbis definitions. The official table contains no `PT_SCE_RELRO`;
  standard `PT_GNU_RELRO` remains separate;
- instruction provenance: address, raw bytes, source file/line, discriminator,
  file offset, and instruction-owned references. The exact method-range Orbis text
  is retained once per method; aggregate references are derived views and are not
  serialized a second time;
- source-artifact metadata: stable method ID, generation status, declaring-header
  includes, generic typed artifact descriptors, content hashes, and eligibility diagnostics;
- structured bundle limitations, including ABI/clobber uncertainty, unvalidated
  semantic equivalence, and the absence of synthesized external declarations.
- deterministic DWARF-derived disassembly target manifest, target-scope hash and policy, valid
  range-list provenance, every retained ELF function candidate, and address/range/name match
  reasons. IDA audit observations are not fields in this production index.

### Implementation-generation validation

artifacts validate-implementation publishes a separate schema-4.1 validation report. Its
`LoadImageProfile` records either the explicit original-address policy or an explicit aligned
load base; DWARF range-list bases are never reused as ELF load bias. `MappedSegment` records map
relocation targets through `PT_LOAD`, while `PT_SCE_DYNLIBDATA` remains metadata-table geometry
only. `RelocationApplication` is a pure formula result with original/evaluated target bytes,
width, overflow status, and an unresolved reason when loader state is absent. `NidBinding` keeps
opaque module/library/version/NID identities and carries the original encoded symbol. A
non-community source-bound database may provide a resolved name directly; a community-derived
mapping is retained as a candidate until its pinned provenance, NID hash, and encoded
library/module context verify. NidBinding records NidResolution, encoded table indexes, and
separate hash/context statuses so demangled spelling, name mapping, and PS4 identity are not
conflated. Conflicts remain failed and are never promoted.

`AbiEvidence` and `InstructionEffects` retain calling-convention/location/CFI and
register/flags/memory/call/stack summaries independently. Missing or conflicting CFI prevents
safety promotion. `CompilerEvidence` records tool hashes, commands, object paths, output hashes,
and stdout/stderr content hashes for the Orbis ABI probe matrix and canonical assembly replay;
implementation validation does not publish raw tool streams or stream paths. A configured timeout
is optional; when a tool actually times out, the evidence retains only the tool, stage, elapsed
time, and configured limit. `SemanticParity` keeps byte,
CFG, external-edge, effect, and live-behavior statuses separate; compilation or matching bytes
alone cannot produce `target-object-equivalent`. Every method also carries a `MethodContextPacket`
joining declaration/implementation DIE/CU identity, ranges, locations, CFI, disassembly,
relocations, NIDs, and bounded diagnostics.

For validation, these packets are served by a `DorisImplementationEvidenceModel`. The complete
analytical manifest pins the source identity and Doris registry publication, while the model
queries typed `die`, `attribute`, `reference`, `range`, `location`, and `frame` families. The
validator never reads Parquet or JSONL rows directly. Parquet generation and native Doris loading
remain one-time producer operations, so the physical model is selected for Doris column pruning,
source/offset key access, and server-side CFI range predicates before the expensive materializer
is run.

The canonical default artifact profile is `canonical-assembly`. For each eligible method it emits
bounded original `.raw.asm` evidence, one exact-byte `.s` compiler input, a deterministic
`implementation-context/1.0` `.context.json` packet, and an SDK-produced `.o` object when
`orbis-as` accepts the `.s`. `.raw.asm` is never assembler input; the context references it rather
than duplicating its text. The core pipeline emits no empty, reference, diagnostic, or `.cpp`
placeholder; a later agentic workflow translates assembly into C++ after the independent evidence
gates. The source-bound Orbis cache remains the authority for complete profile stdout/stderr.

### Implementation Artifact Descriptor

Each generated method artifact is described by:

- `kind`: `raw-assembly`, `canonical-assembly`, `object`, or `context`;
- `path`: a safe path relative to the implementation bundle;
- `sha256`: the exact generated artifact hash;
- `role`, `content_type`, `byte_length`, and optional `producer` identity.

The bundle manifest is a publication envelope rather than another evidence index. It records the
artifact profile, report/header/source identities, report hash, aggregate bundle digest, file
count, and publication status. Method evidence remains only in the canonical report.

The cache key includes the schema, parser, source/tool identities, root symbol, and consumed
profile flags, including the standard relocation profile, generic and target-aware LLVM
identities/triples, and the SDK-definition fingerprint. Known-invalid SDK profiles are excluded
from the execution plan and documented once; they are not retained as repeated unavailable rows.

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
