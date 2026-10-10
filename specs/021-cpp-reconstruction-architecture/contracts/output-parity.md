# Output integrity and equivalence

> **Archived Python project:** This page describes the frozen Python snapshot.
> Development has moved to an unpublished Rust rewrite. See [archive status](../../../docs/reference/project-status.md).

For reviewers, this reference separates proof that a bundle is internally valid from proof that
it matches the initial producer. Real artifacts stay outside source control.

- Inventory every relative path and byte length; reject missing, additional, unsafe, duplicate,
  temporary, symlinked, or unexpectedly empty artifacts.
- Validate manifest-owned hashes and byte counts before comparing evidence. Unknown fields
  participate in equality rather than being discarded.
- Headers and applicable `.asm`/`.s` are byte-exact. Establish `.o` repeatability with the same
  executable/profile before using byte equality. No implicit binary-section normalization.
- Root statuses, candidates, ownership, aliases, offsets, source identities, conflicts,
  diagnostics, tool identities, and output membership are invariant.
- Report metadata normalization requires explicit field paths and unchanged-code paired
  evidence. A key name alone does not authorize normalization anywhere in a document.
- Keep each original file hash even when a report receives a separate equivalence digest.
- Context-disabled mode omits application manifests; the external inventory remains required.
- Missing or rejected method evidence is an explicit baseline limitation, not successful
  assembly or semantic validation. Compiler observations remain a separate result.

No changed header expectation may be accepted inside this refactor. Record a separate behavior
proposal and obtain explicit acceptance before altering that contract.
