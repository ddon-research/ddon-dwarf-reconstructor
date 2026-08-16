# Python API reference

This reference is for developers who need the source-level Python contracts behind the DDON DWARF
Reconstructor. It is an exhaustive inventory of modules under `src/ddon_dwarf_reconstructor`,
including infrastructure and parser internals. The inventory is intentionally broader than the
stable public API: a module or member appearing here is not a promise that it is supported for
external callers.

The declaration pages are generated from source paths by
[`tools/documentation/generate_api_reference.py`](../../tools/documentation/generate_api_reference.py).
The generator performs no package imports and emits one `:::` directive per module; Zensical's
preliminary mkdocstrings integration resolves those directives during the strict site build.
Generated pages should not be edited by hand. Refresh them with `uv run just docs-api`, and verify
that the checked-in output is current with `uv run just docs-api-check`.

## Module groups

- [Root modules](generated/root.md) — package exports, CLI composition, and top-level helpers.
- [Application modules](generated/application.md) — use cases and orchestration.
- [Core modules](generated/core.md) — shared contracts and cross-cutting policies.
- [Domain modules](generated/domain.md) — models, ports, and domain services.
- [Infrastructure modules](generated/infrastructure.md) — ELF/DWARF, storage, tooling, and runtime
  adapters.
- [Utility modules](generated/utilities.md) — supporting implementation utilities.

The rendered pages expose signatures, annotations, Google-style docstrings, inherited members, and
source-derived member ordering. The right-hand “On this page” navigation and section permalink
anchors come from the existing Zensical TOC configuration; this landing page deliberately contains
no in-page TOC marker.
