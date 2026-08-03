# DWARF tag classification

Tag classification is centralized in `domain/models/dwarf/tag_constants.py` and
`domain/services/parsing/die_type_classifier.py`. The classifier distinguishes class/struct/union,
enumeration, typedef, base/qualifier, pointer/reference, array, function, and declaration-only
forms before type-chain traversal.

## Why the distinction matters

DWARF references do not copy a complete type. A declaration can be encountered before the sized
definition, and a typedef or qualifier can wrap the terminal type. The parser therefore follows
references lazily, retains DIE/CU offsets, and chooses a complete definition through the shared
selection policy.

## Update rule

When a tag is added or reclassified, update the classifier, the type-chain tests, the generated
header/knowledge export expectations, and the relevant Spec Kit feature. Do not add an alternate
classification table in a generator or documentation-only code path.

The [DWARF 2-4 audit](../../knowledge-base/dwarf/dwarf2-4-correctness-audit.md) records normative
cross-checks against the generated specification artifacts.
