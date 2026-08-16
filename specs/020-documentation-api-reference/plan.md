# Implementation plan

1. Inventory the existing Zensical configuration, PEP 735 docs group, Pages workflow, documentation
   instructions, source package layout, and test taxonomy while preserving unrelated worktree edits.
2. Add the locked `mkdocstrings-python` docs dependency and configure the preliminary Zensical
   handler, standard-library inventory, Google docstrings, inherited members, source-hidden output,
   deterministic ordering, rendered headings, and the existing sidebar TOC depth/follow behavior.
3. Implement the standard-library generator at
   `tools/documentation/generate_api_reference.py`; cover package conversion, fixed groups,
   deterministic ordering, duplicate/unexpected-group failures, atomic writes, and stale-output
   `--check` behavior with focused quality tests.
4. Generate `docs/api/generated/`, add the API landing page and explicit navigation, and make
   `docs-api-check` a prerequisite of both `docs-build` and `docs-check` without changing the Pages
   workflow shape.
5. Synchronize README, documentation system/deployment explanations, authoring and validation
   how-tos, documentation style, contributor adapters, roadmap, and this feature record. Label the
   exhaustive inventory and preliminary handler/backlink boundary explicitly.
6. Run dependency lock checks, API generation/checks, focused tests, Node validators, strict site
   build, and the required root quality/test/coverage/audit loop. Inspect rendered headings,
   signatures, annotations, anchors, sidebar TOCs, directive resolution, and strict-build output.
