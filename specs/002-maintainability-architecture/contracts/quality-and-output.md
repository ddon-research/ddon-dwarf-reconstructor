# Quality and Output Contracts

## Structural contract

The checker applies to all non-generated Python under `src/` and `tests/`:

| Item | Maximum |
| --- | ---: |
| Module | 600 physical lines |
| Class | 500 physical lines, including documentation |
| Function or method | 75 physical lines |
| McCabe complexity | 10 |

## Output contract

Header and C++ output files are compared byte-for-byte using sorted relative
paths, byte lengths, and SHA-256 digests. JSONL and deterministic manifests use
the same comparison. Volatile metadata is excluded only through an explicit,
versioned normalization rule.

Every baseline records input identity, producer identity, configuration, and
cache state. Real-asset baselines remain outside source control.

## Layer contract

Domain code depends only on domain models, ports, and standard-library
abstractions. Application code coordinates use cases and ports. Infrastructure
implements ports for ELF/DWARF, compressed dumps, SQLite, caches, disassembly,
and filesystem/process access. The composition root may construct adapters.
