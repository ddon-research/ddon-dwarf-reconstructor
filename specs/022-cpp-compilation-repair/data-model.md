# Data model: Repair contracts

> **Archived Python project:** This page describes the frozen Python snapshot.
> Development has moved to an unpublished Rust rewrite. See [archive status](../../docs/reference/project-status.md).

This design reference describes additive contracts for the existing pipeline. These fields are
requirements for implementation, not a claim that every current model already supplies them.

## Evidence and Identity

`EvidenceLocator` binds source identity, CU offset, DIE offset, tag, and optional source location.
Zero is valid. A qualified display name is not a unique evidence locator. Equivalent observations
may resolve to one declaration only through recorded compatibility rules; disagreements survive.

`TypeReference` and `TypeScope` remain the canonical declarator and lexical-context models.
Ordered modifiers preserve pointer/reference/array/callable/member-pointer precedence. Template
arguments retain full qualified identity and parameter kind; no flattening before deduplication.

## Declaration Facts

| Entity | Required facts and invariants |
| --- | --- |
| Alias | Alias identity, lexical owner, target reference, all evidence locators, resolution status; multiple aliases may share one anonymous target |
| Enum | Scopedness including unknown, underlying representation, fixed-base evidence status, enumerators, lexical scope, size and provenance; unknown is not false |
| Template family | Qualified primary identity, evidenced parameter kinds/order/packs, concrete arguments, observations, conflicts; one primary authority |
| Method | Overload identity distinct from compatibility facts including return/exception/access/static/virtual evidence |
| Member | Structured type, storage/access, bit size including zero, bit/data offset evidence, source provenance; legal type/width checked |
| Base | Referenced type identity, access, virtualness and actual location evidence; existing `base_class_offsets` are DIE references, not byte displacements |

## Dependency Requirement

A requirement contains consumer ID, provider ID, kind, lexical context, reason, and contributing
evidence. Kinds are `declaration`, `alias_declaration`, `enclosing_owner`, `template_primary`, and
`complete_definition`. Multiple kinds may apply to one type use; they are not one boolean strength.
For example, `Alias*` needs the alias declaration, while `Outer::Inner*` needs visible owner/member
declarations. A pointer alone does not erase either obligation.

Resolve requirements before assigning files. Legal declarations can satisfy requirements without
includes when co-located. Include graph SCCs are derived publication constraints, not proof of a
cycle in C++ inheritance or complete-type requirements.

## Publication and Acceptance State

The publication ledger joins requested root, resolved declaration, emission owner, output path,
source locators, and file hash. Omission/conflict diagnostics carry IDs and reasons. Validation
records join by output identity and content hash, not a simple class-name regex.

Each acceptance dimension uses `passed`, `failed`, `blocked`, or `not_observed`, with command,
producer/source/profile identity and retained evidence. A residual blocker changes its own state
from `observed` to `reproduced` to `handed_off` or `resolved`; `handed_off` cannot set feature
acceptance to `passed`.
