---
description: 'Claude adapter for the DDON DWARF reconstructor'
applyTo: '**/*'
---

# Claude project adapter

`AGENTS.md` is the canonical repository instruction source. The Python-specific rules in
`.github/instructions/python.instructions.md` apply to Python files; this file only supplies the
same tool loop for Claude-compatible clients.

## Development loop

Use regular CPython 3.14.6 and the locked uv environment:

```text
uv sync --python 3.14.6
uv run just test-unit
uv run just check
uv run just test
uv run just coverage
```

Use the unified root CLI:

```text
uv run ddon-dwarf-reconstructor generate resources/DDOORBIS.elf --symbol MtObject
uv run ddon-dwarf-reconstructor generate resources/DDOORBIS.elf --symbol MtObject --full-hierarchy
uv run ddon-dwarf-reconstructor generate resources/DDOORBIS.elf --symbols-file resources/season2-resources.txt
uv run ddon-dwarf-reconstructor artifacts inspect --elf resources/DDOORBIS.elf
```

The standalone specification tool is run from its own project boundary:

```text
uv run --directory tools/dwarf_spec_pipeline just check
uv run --directory tools/dwarf_spec_pipeline dwarf-spec-pipeline validate
```

## Engineering constraints

- Preserve immutable input identity, source-bound durable caches, atomic publication, deterministic
  ordering, qualified names, offsets, layouts, provenance, and generated-header bytes.
- Keep domain, application, and infrastructure boundaries intact. New CLI code belongs at the
  composition root and must convert into typed application requests.
- Do not commit ELF files, expanded dumps, generated headers, caches, logs, credentials, or real
  performance artifacts.
- Use explicit local paths for real PS4 and compiler validation; retain cold/warm state and record
  the manifest identity.
- Update the README, architecture/testing docs, active contracts, and Spec Kit artifacts whenever
  public commands, configuration, or validation behavior changes.
