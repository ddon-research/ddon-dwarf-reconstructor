# Architecture contract

> **Archived Python project:** This page describes the frozen Python snapshot.
> Development has moved to an unpublished Rust rewrite. See [archive status](../../../docs/reference/project-status.md).

For implementers, this reference constrains the refactoring without promising new reconstruction
features. Domain policies depend on core protocols, domain values/ports, and the standard library;
application code coordinates through ports; infrastructure owns external libraries and I/O.

- Existing control-flow/effect/ABI value objects and pure policies move under matching
  `domain/models/cpp_reconstruction/` and `domain/services/cpp_reconstruction/` namespaces.
- Keep tool-output parsing, raw DIE adaptation, source identity, subprocesses, and filesystem
  publication in their owning adapters. Preserve source/CU/DIE identities and uncertainty.
- Extend existing ports before introducing narrow assembler/linker/metadata capabilities.
  A generic compiler service is not required. Composition roots construct concrete adapters.
- Use typed requests for cohesive operations; immutable published values may contain separately
  owned mutable session state only when that lifetime is explicit and tested.
- Preserve public CLI/artifact behavior; move internal callers atomically without shims.
- No global cache may mix sources or outlive its validated producer/configuration identity.
- Preserve optional strict validation isolation and canonical header/type/selection policies.

Test unit policy without SDK/ELF I/O, adapter behavior with bounded fake processes, application
wiring with fake ports, and real publication against the independent baseline.
