# Documentation validators

> **Archived Python project:** This page describes the frozen Python snapshot.
> Development has moved to an unpublished Rust rewrite. See [archive status](../../docs/reference/project-status.md).

This directory contains the locked Node.js tools used by the repository documentation loop. It is
not a second application project or a replacement for the root `uv` project.

The sibling `generate_api_reference.py` is a standard-library source inventory tool. It writes the
checked-in `docs/api/generated/` Markdown declaration pages consumed by Zensical's preliminary
mkdocstrings integration; it does not import the application or render HTML.

## Tools

- [`@mermaid-js/mermaid-cli`](https://github.com/mermaid-js/mermaid-cli) `11.16.0` renders every
  Mermaid fence in `docs/` and `README.md` to a temporary SVG. The SVGs are validation artifacts
  only and are never written to the repository.
- [`markdownlint-cli2`](https://github.com/DavidAnson/markdownlint-cli2) `0.23.2` validates the
  authored site Markdown with `.markdownlint-cli2.jsonc`. Generated DWARF specification and
  Python API declaration pages are excluded because their formatting is owned by their generators;
  the strict Zensical build remains responsible for parsing and rendering them.

The official Node Mermaid CLI is used instead of the similarly named Python package or a second
Mermaid lint implementation. This keeps rendering behavior aligned with the Mermaid JavaScript
implementation already used by the static site and avoids maintaining two syntax authorities.

## Commands

From the repository root:

```powershell
uv run just docs-tools-install
uv run just docs-api
uv run just docs-api-check
uv run just docs-lint
uv run just docs-diagrams
uv run just docs-check
```

`docs-tools-install` is needed after a fresh checkout or a change to `package-lock.json`. The
normal `uv run just check` recipe includes `docs-check`; CI installs the lockfile before invoking
the same recipe.
