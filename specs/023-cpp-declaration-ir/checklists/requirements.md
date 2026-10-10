# Specification readiness: Declaration IR

> **Archived Python project:** This page describes the frozen Python snapshot.
> Development has moved to an unpublished Rust rewrite. See [archive status](../../../docs/reference/project-status.md).

This checklist evaluates design readiness, not a completed compiler integration.

- [x] Entry condition is Feature 022 repair or a demonstrated source-bound blocker handoff.
- [x] Prioritized stories, edge cases, requirements, and measurable outcomes are present.
- [x] Requirement/task coverage and dependency order are explicit.
- [x] Observations, semantic identity, and emission decisions are separate typed contracts.
- [x] Compiler facts are additive and cannot silently replace source evidence.
- [x] Normal generation remains compiler-independent; adapters stay outside the domain.
- [x] Pinned subprocess validation is the initial direction; native adoption needs evidence.
- [x] Research compares common fixtures, licensing, Windows packaging, omissions, and costs.
- [x] Migration includes removal of superseded policy, differential tests, and full-corpus gates.
- [x] Host syntax, target ABI, determinism, and performance have separate evidence dimensions.
- [x] Constitution review requests no exception or speculative dependency promotion.
- [ ] Tool comparison, migration, compiler integration, and final acceptance have passed.

Documentation lint/build outcomes are recorded in [measured evidence](../measured-evidence.md).
The research prompt and adapter contract are deliverables; their existence is not execution
evidence for future implementation tasks.
