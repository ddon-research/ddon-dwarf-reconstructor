# Research: Repair decisions and rejected assumptions

> **Archived Python project:** This page describes the frozen Python snapshot.
> Development has moved to an unpublished Rust rewrite. See [archive status](../../docs/reference/project-status.md).

This record serves reviewers of the September 20 working tree and Gemini proposal. It separates
observed defects from language constraints and future implementation decisions. See
[measured evidence](measured-evidence.md) for run boundaries and retained report identities.

## Decisions

| Decision | Rationale | Alternative considered |
| --- | --- | --- |
| Retain structured references and DWARF ancestry | Preserve declarator precedence and distinguish namespaces from aggregate owners | Hardcoded namespace lists and `::` splitting lose semantic context |
| Keep explicit specializations by default | Concrete observations do not prove a generic body | Cross-instantiation member unions fabricate behavior |
| Repair evidence and identity before adding a compiler library | Reviewed failures occur before C++ parsing | A library cannot restore an identity already erased by deduplication |
| Use distinct declaration requirements | Pointer/reference use can still require an alias or owner | Universal include-over-forward adds false completeness edges |
| Reuse existing deterministic SCC implementation | `header_cycles.py` already provides graph machinery | NetworkX is not justified just to obtain Tarjan SCCs |
| Diagnose current Doris health before repair | September 20 read-only liveness checks succeeded | Blind marker deletion or volume replacement risks retained evidence |

## C++ language corrections

`class Outer { public: class Inner; };` defines `Outer`; it is not a forward-declaration wrapper
that can later be extended with real fields. Declare `Inner` inside the actual owner definition,
then define it outside only where legal. An external user naming `Outer::Inner` needs owner/member
visibility; by-value use also requires the inner type to be complete. See
[nested classes](https://eel.is/c++draft/class.nest).

Aliases have declarations, not independent forward declarations. However, `class Target; using
Alias = Target;` makes `Alias*` legal without defining `Target`. An alias-availability dependency
must not automatically become a complete-target dependency.

An opaque unscoped enum declaration requires an enum base; scoped and unscoped redeclarations
must agree. A DWARF underlying type reports representation, not necessarily the original source's
explicit fixed-base syntax. Do not infer scopedness or emit `enum class` for every named enum.
See [enumeration declarations](https://eel.is/c++draft/dcl.enum) and
[DWARF enumeration underlying-type proposal](https://dwarfstd.org/issues/040618.1.html).

Exception specifications cannot alone distinguish overloads. Return type, access, and virtualness
also need compatibility checking separately from the overload key. Compiler fixtures must test
the target language profile rather than use the current method tuple as the expected result.

## Observed code gaps to repair

Paths below are relative to `src/ddon_dwarf_reconstructor/`.

| Surface | Observed gap | Owning task |
| --- | --- | --- |
| `domain/services/generation/alias_rendering.py` | Earlier review reproduced a removed self edge; specification-time recheck finds self edges retained and all seven alias tests passing; preserve this repair | T003 |
| `domain/services/parsing/class_parser_children.py` | Anonymous target map retains one alias; enum fallback naming defeats anonymous detection | T004 |
| `domain/services/generation/header_hierarchy.py` | Unqualification collapses `Box<left::Item>` and `Box<right::Item>` | T005 |
| `domain/services/generation/special_header_renderer.py`, `header_type_planning.py`, `template_forward_declarations.py` | Primary scope/signature still inferred independently; numeric spellings become unsigned parameters | T006 |
| `domain/services/generation/method_signature_policy.py`, `template_families.py` | Overload identity includes fields that should instead detect incompatible declarations | T007 |
| `domain/models/dwarf/enum_info.py`, `domain/services/generation/header_aggregate_rendering.py` | Evidence model lacks scopedness/base provenance; named enums become scoped enums | T008 |
| `domain/services/generation/header_member_rendering.py` | Zero-width unnamed bitfields are dropped; identifier-shaped types are accepted without type evidence | T008 |
| `domain/services/parsing/array_parser.py`, `domain/services/generation/header_hierarchy.py` | Array-order disagreement and object-ID/mapping-length cache identity need canonicalization | T009 |
| `domain/services/generation/header_ordering.py` | Pointer/static shortcuts skip alias and enclosing-owner prerequisites | T010 |
| `application/generators/symbol_header_validation.py` | Definition parsing loses qualified nested identity; origin matching splits on first `::` | T012 |

These findings do not mean every compiler diagnostic has been mapped. T001 and T013 reconcile
remaining real-source families, including `cLimit`, `MtProperty`, nested `cTree` arguments, and
material/audio/UI types, before choosing repairs. A missing diagnostic name does not prove a
missing header: it may be an identity, completeness, publication, or compiler-cascade problem.

## A representation limit to investigate

The following ordinary source pattern compiles in the reviewed Clang canary:

```cpp
template<class T> struct Box { T value; };
struct Outer { struct Inner { int x; }; Box<Inner> value; };
```

Replacing the primary body with a forward declaration and placing an explicit
`Box<Outer::Inner>` definition after `Outer` fails because `Outer` needs the specialization
complete first. This is a language counterexample, not proof that a DDON case is irreducible.
A real handoff requires exact source/CU/DIE evidence and a minimal reproduction. Co-location
alone cannot solve a cyclic declaration requirement. Unsupported generic reconstruction stays
diagnosed; the successor may research a justified representation without guessing a body.

## Operational correction

Gemini's counts and quality failures were stale at review time: one unit test failed,
Ruff/structure/type checks passed, and three files failed formatting. At specification-time recheck,
the seven alias tests passed and only two source files still failed formatting. Doris was alive and bounded
source-bound queries succeeded. The quoted September 20 error cannot by itself establish the
cause of a September 17 halt. Preserve outage evidence and chronology, and verify the actual
database/schema/volume before any recovery action. No storage repair was performed in the review.
