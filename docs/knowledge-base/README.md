# Knowledge base

The knowledge base preserves research notes, generated specifications, and bounded external
evidence that support the deterministic reconstructor. It is intentionally different from the
reference pages: a note may be exploratory or historical, while a reference page states a current
contract only after it is backed by source and tests.

## Authority labels

- **Producer fact:** emitted by the owning DWARF/ELF producer and retained by the reconstructor.
- **Deterministic cross-check:** derived from checked-in fixtures, manifests, or generated
  specification artifacts.
- **External additive evidence:** produced by Orbis or generic comparison tools and bound to a
  source/tool/profile/output manifest.
- **Research note:** useful context that must be revalidated before becoming a runtime contract.

## Sections

| Section | Contents |
| --- | --- |
| [DWARF](dwarf/dwarf2-4-correctness-audit.md) | DWARF 2-4 correctness, parser comparisons, and normative relationships |
| [PS4 ELF](ps4-elf/ps4-constants.md) | platform constants and loader research |
| [pyelftools](pyelftools/pyelftools-approach.md) | API usage and parser integration notes |
| [Tools](tools/external-tool-evidence.md) | bounded external-tool profiles and authority boundaries |
| [Observability](observability/README.md) | structured events, tracebacks, and telemetry seams |
| [Testing](testing/README.md) | taxonomy, CI evidence, and validation loop records |
| [Performance](performance/README.md) | profiler decisions, source-bound metrics, and static benchmark history |
| [DWARF specification pipeline](dwarf-specification/README.md) | official-source JSON/Markdown artifacts and manifests |

The [static site home](../index.md) and [documentation system explanation](../explanation/documentation-system.md)
describe how these notes relate to tutorials, how-to guides, reference pages, and specs.

## Contribution rule

Add actionable evidence, source links, status, and the next validation step. Do not copy an entire
implementation into a note or leave a “future” claim after the source has implemented it. Update
the corresponding reference page or delete the note when it no longer adds information.
