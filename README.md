# DDON DWARF Reconstructor

Reconstructs C++ class definitions from DWARF debug information in ELF files. Developed for Dragon's Dogma Online modding.

## Features

- **Complete dependency resolution:** Recursively resolves all type dependencies
- **Full class definitions:** Generates complete headers with all dependent classes (not just forward declarations)
- **Inheritance hierarchies:** Complete base-to-derived chains with automatic ordering
- **Multi-CU type resolution:** Searches all compilation units to find complete definitions, preferring them over forward declarations
- **Type-aware scoring:** Distinguishes typedefs, base types, enums, and classes with intelligent completeness scoring
- **Type resolution:** Handles typedefs, pointers, references, arrays
- **Memory layout analysis:** Packing suggestions and padding detection
- **Platform support:** PS4 (x86-64, DWARF3/4) and PS3 (PowerPC64, DWARF2) with automatic detection
- **Output organization:** Platform-specific output folders (output/ps4/, output/ps3/)
- **PS4 ELF support:** Automatic section patching for PS4 binaries
- **High performance:** Persistent caching, offset-based resolution, streaming dump indexing, and bounded search
- **Robust architecture:** Domain-driven design, source-bound artifacts, deterministic outputs, and focused validation tiers

## Requirements

- Regular CPython 3.14.6
- ELF file with DWARF debug information

## Installation

```bash
uv sync --python 3.14.6 --extra dev
uv run pytest -m unit  # verify
```

## Usage

### Python Script

```bash
# Single class (PS4)
uv run python main.py resources/DDOORBIS.elf --generate MtObject

# Multiple classes (PS4)
uv run python main.py resources/DDOORBIS.elf --generate MtObject,MtVector4,rTbl2Base

# Full hierarchy - Multi-file (NEW DEFAULT, PS4)
uv run python main.py resources/DDOORBIS.elf --generate ClassName --full-hierarchy

# Full hierarchy - Single file (LEGACY, PS4)
uv run python main.py resources/DDOORBIS.elf --generate ClassName --full-hierarchy --single-file

# PS3 single class
uv run python main.py resources/PS3/EBOOT.ELF --generate MtDTI

# PS3 multiple classes
uv run python main.py resources/PS3/EBOOT.ELF --generate MtUI,rLayout

# PS3 full hierarchy - Multi-file
uv run python main.py resources/PS3/EBOOT.ELF --generate rLayout --full-hierarchy

# Batch processing from file (PS4, one symbol per line)
uv run python main.py resources/DDOORBIS.elf --symbols-file resources/season2-resources.txt

# Batch processing with multi-file hierarchy (289 symbols validated, PS4)
uv run python main.py resources/DDOORBIS.elf --symbols-file resources/season2-resources.txt --full-hierarchy

# Exhaustive search for multi-definition symbols (PS4)
uv run python main.py resources/DDOORBIS.elf --generate rLayout --exhaustive

# Fast exhaustive search with precomputed DWARF dump (PS4)
uv run python main.py resources/DDOORBIS.elf --generate rLayout --exhaustive \
  --dwarf-dump path/to/DDOORBIS.elf.llvmdwarfdump.zst

# Exhaustive search using an environment-provided dump path
DDON_DWARF_DUMP_PATH=/path/to/DDOORBIS.elf.llvmdwarfdump.zst \
uv run python main.py resources/DDOORBIS.elf --generate rLayout --exhaustive

# Knowledge export with optional pinned Orbis validation
uv run ddon-dwarf-reconstructor resources/DDOORBIS.elf --generate rLayout \
  --dwarf-dump path/to/DDOORBIS.elf.llvmdwarfdump.zst \
  --dwarf-index output/real-dump-index/DDOORBIS.elf.llvmdwarfdump.index.sqlite3 \
  --export-knowledge output/rLayout --build-id ps4-02020005 \
  --orbis-objdump 'D:/SCE/ORBIS SDKs/8.000/host_tools/bin/orbis-objdump.exe'

# With options
uv run python main.py resources/DDOORBIS.elf --generate ClassName --output dir/ --verbose
```

### Exhaustive Search Mode

**Problem:** Some symbols (like `rLayout`) have multiple definitions across compilation units with varying completeness (some missing nested enums/structs).

**Solution:** `--exhaustive` mode scans all definitions and selects the most complete one based on scoring:
- **Byte size:** +1 per byte
- **Nested enums:** +1000 each
- **Nested structs:** +500 each
- **Nested unions:** +300 each

**Performance:**
- Compressed-dump index build (one-time, real 30+ GB dump): 295.6 seconds
- Fresh-process indexed class + method lookup pair: 1.52 ms
- Warm real `rLayout` knowledge export: about 2.4 seconds
- Direct full-CU scan remains a slow fallback when no dump/index is available

**Behavior note:**
- Exhaustive matching is intended for the explicitly requested root symbol.
- Follow-up base-class and dependency resolution should stay on the fast path so
  the exporter does not cascade into exhaustive scans for common types such as
  `cResource` after the root symbol has already been selected.

**Usage:**
```bash
# Standard exhaustive (slow but thorough)
uv run python main.py resources/DDOORBIS.elf --generate rLayout --exhaustive

# Fast exhaustive with compressed dump file
uv run python main.py resources/DDOORBIS.elf --generate rLayout --exhaustive \
  --dwarf-dump /path/to/llvm-dwarfdump-output.zst

# Environment variable discovery
DDON_DWARF_DUMP_PATH=/path/to/llvm-dwarfdump-output.zst \
uv run python main.py resources/DDOORBIS.elf --generate rLayout --exhaustive
```

If `--dwarf-dump` is omitted, exhaustive root lookup now tries these sources in
order:

1. `--dwarf-dump`
2. `DDON_DWARF_DUMP_PATH`
3. a sibling file named `DDOORBIS.elf.llvmdwarfdump.zst` next to the ELF

**Cache Behavior:**
- The first dump-assisted search atomically builds
  `<dump>.index.sqlite3`; keep this 164 MiB deterministic sidecar
- Exhaustive search populates the symbol cache with the best definition found
- Subsequent fresh-process runs reuse both durable artifacts
- Symbol caches are stored in the OS-local cache directory (or
  `DWARF_CACHE_DIR`) and are isolated by a digest of the resolved ELF path

**DWARF Dump Creation:**
```bash
# Create compressed dump for fast exhaustive searches
llvm-dwarfdump DDOORBIS.elf > DDOORBIS.elf.llvmdwarfdump
zstd -19 DDOORBIS.elf.llvmdwarfdump -o DDOORBIS.elf.llvmdwarfdump.zst
# Size: ~1GB compressed (30GB+ uncompressed)
```

### Full Hierarchy Modes

**Multi-file (DEFAULT)** - Recommended for large hierarchies

- Organizes classes by source file (DW_AT_decl_file mapping)
- Generates separate headers per file (more maintainable)
- Includes #include statements between files
- Cache system: `.cache/{elf_name}_headers.json`
- Example output: 22 files for MtObject hierarchy

```bash
uv run python main.py resources/DDOORBIS.elf --generate MtObject --full-hierarchy
# Output: output/ps4/MtObject.h, MtProperty.h, MtUI.h, etc.
```

**Single-file (LEGACY)** - Use `--single-file` flag

- All classes in one file with forward declarations
- No #include dependencies
- Original behavior preserved for backward compatibility

```bash
uv run python main.py resources/DDOORBIS.elf --generate MtObject --full-hierarchy --single-file
# Output: output/ps4/MtObject.h (all classes in one file)
````


### Native Executable

```bash
# Build native executable (requires clang)
make build

# Run compiled executable
build/main.exe --generate MtObject resources/DDOORBIS.elf
build/main.exe --generate ClassName --full-hierarchy resources/DDOORBIS.elf
```

### Configuration

```bash
# Configuration via .env
ELF_FILE_PATH=resources/DDOORBIS.elf
OUTPUT_DIR=output
VERBOSE=false

# Options
--output DIR          # output directory (default: ./output)
--verbose             # enable debug logging
--full-hierarchy      # include all base classes (multi-file mode by default)
--single-file         # legacy mode: single file with all classes
--generate SYMBOL     # generate for single or multiple symbols (comma-separated)
--symbols-file FILE   # read symbols from file (one per line, alternative to --generate)
--exhaustive          # scan all CUs for most complete definition (slow but thorough)
--dwarf-dump PATH     # compressed llvm-dwarfdump output used for indexed lookups
--dwarf-index PATH    # explicit durable SQLite sidecar for --dwarf-dump
--export-knowledge DIR # deterministic JSONL graph bundle output
--build-id ID         # stable build identifier used by knowledge export
--orbis-objdump PATH  # pinned PS4 SDK disassembler used with knowledge export
```

### Agent Tracing

Run the local Langfuse stack for GitHub Copilot and OpenAI Codex:

```powershell
Copy-Item ops/langfuse/.env.example ops/langfuse/.env
# Replace the REPLACE_WITH values in ops/langfuse/.env.
docker compose --project-name ddon-langfuse --file ops/langfuse/compose.yaml --env-file ops/langfuse/.env config --quiet
docker compose --project-name ddon-langfuse --file ops/langfuse/compose.yaml --env-file ops/langfuse/.env up -d
docker compose --project-name ddon-langfuse --file ops/langfuse/compose.yaml --env-file ops/langfuse/.env logs --tail 200 langfuse-web
```

Configure Docker Desktop auto-start, VS Code Copilot, and Codex using
[docs/LANGFUSE_TRACING.md](docs/LANGFUSE_TRACING.md). Full-content capture stores prompts,
responses, reasoning summaries, and tool arguments in the local Langfuse volumes.

### Caching System

The project uses two caching mechanisms for optimal performance:

#### 1. Symbol Cache (DWARF Offset Cache)

**Location:** `%LOCALAPPDATA%\ddon-dwarf-reconstructor` on Windows,
`$XDG_CACHE_HOME/ddon-dwarf-reconstructor` when configured, otherwise
`~/.cache/ddon-dwarf-reconstructor`. Set `DWARF_CACHE_DIR` to override it.

**Purpose:** Caches symbol→CU/DIE offset mappings with multi-definition support

**Cache Format:** v4.0 (migrates validated older formats)

**How It Works:**
1. First search (any mode) stores symbol location (CU offset + DIE offset + score + completeness)
2. **Multi-definition support**: Stores ALL definitions of a symbol across different CUs
3. Automatically selects best definition (highest score among complete definitions)
4. Subsequent lookups use cached best offset for O(1) retrieval
5. Exhaustive search **always populates cache** with all definitions found
6. Cache grows asymptotically to cover all regular use cases

**Multi-Definition Handling:**
- Symbols like `rLayout` may appear in multiple CUs with varying completeness
- Cache stores metadata for each definition: `cu_offset`, `die_offset`, `score`, `complete`
- Best definition automatically selected based on:
  1. Completeness (prefer complete over forward declarations)
  2. Score (nested types: enums×1000 + structs×500 + unions×300 + byte_size)

**Performance:**
- Warm real `rLayout` knowledge export: 1.57-1.59 seconds
- Fresh-process compressed-index lookup pair: 1.52 ms
- Cold compressed-index construction: 295.6 seconds on the reference dump

**Artifact inspection and recovery:**
```powershell
uv run ddon-dwarf-artifacts inspect --elf resources/DDOORBIS.elf `
  --dwarf-dump D:/research/.../DDOORBIS.elf.llvmdwarfdump.zst `
  --dump-index output/real-dump-index/DDOORBIS.elf.llvmdwarfdump.index.sqlite3

# Force a full content verification instead of the immutable-input fast path.
uv run ddon-dwarf-artifacts verify-source resources/DDOORBIS.elf

# Upgrade/repair a compatible legacy sidecar without rescanning the dump.
uv run ddon-dwarf-artifacts repair-dump-index D:/research/.../dump.zst `
  --index-path output/real-dump-index/dump.index.sqlite3

# Deliberate recovery operations.
uv run ddon-dwarf-artifacts rebuild-dump-index D:/research/.../dump.zst `
  --index-path output/real-dump-index/dump.index.sqlite3
uv run ddon-dwarf-artifacts repair-symbol-cache --elf resources/DDOORBIS.elf `
  --from-cache resources/.cache/DDOORBIS_dwarf_cache.json
uv run ddon-dwarf-artifacts repair-catalog
```

`purge-dump-index` additionally requires `--confirm-index-path` with the exact
resolved target. Prefer repair or rebuild; purge is intentionally targeted.

**Example:**
```bash
# First run builds/reuses the dump index and populates symbol definitions
uv run ddon-dwarf-reconstructor resources/DDOORBIS.elf --generate rLayout `
  --dwarf-dump dump.zst --dwarf-index dump.index.sqlite3 `
  --export-knowledge output/rLayout `
  --orbis-objdump 'D:/SCE/ORBIS SDKs/8.000/host_tools/bin/orbis-objdump.exe'

# Later fresh processes reuse the same artifacts and reproduce the bundle.
uv run ddon-dwarf-reconstructor resources/DDOORBIS.elf --generate rLayout `
  --dwarf-dump dump.zst --dwarf-index dump.index.sqlite3 `
  --export-knowledge output/rLayout-rerun `
  --orbis-objdump 'D:/SCE/ORBIS SDKs/8.000/host_tools/bin/orbis-objdump.exe'
```

The Orbis option is intentionally explicit. Generic GNU/LLVM objdump is not a
compatible substitute for the proprietary PS4 ELF. The pilot baseline is SDK
8.000's `orbis-objdump`, target `elf64-x86-64-freebsd`. Its bounded report is
cached under the durable artifact directory using the ELF hash, executable
hash/version, target, parser version, flags, and root symbol. A knowledge export
then adds `instructions.jsonl`, producer-scoped function/evidence nodes, direct
`CALLS` edges, and a declarations-only `reconstructed.hpp`. Indirect calls are
retained as instructions but are not promoted to invented graph targets.

On the reference PS4 `02020005` inputs, `rLayout::load(MtStream&)` occupies the
half-open range `[0x693e60, 0x694ae5)`. The current report contains 747 decoded
instructions and 58 call instructions (56 direct and two indirect). Warm runs
reuse the validated report and reproduce the graph, instruction, and header
files byte-for-byte. The manifest remains `partial` when a concrete DWARF field
type cannot be placed in the structural closure; the unresolved type is kept as
a logical reference with a diagnostic instead of being silently dropped.

For knowledge export of `ps4-02020005/rLayout`, the producer applies a golden
root-authority contract before consulting ambiguous symbol-cache candidates. It
resolves DIE `0x117ec452` directly, validates the recovered layout and nearby
`MyDTI` evidence, and records both the selection basis and rejected duplicate
`0x76133` in `manifest.root_authority`. `--exhaustive` is no longer required to
obtain the approved root for this build/symbol pair; it remains useful for
auditing unpinned symbols.

#### 2. Header Cache (SHA256 Cache)

Multi-file hierarchy generation uses SHA256-based caching for performance:

**Location:** `.cache/{elf_name}_headers.json`

**How It Works:**
1. Computes SHA256 hash of each generated header
2. Persists hashes and timestamps to JSON cache file
3. On regeneration: checks if content matches (no file written if unchanged)
4. Automatic invalidation when content changes

**Performance:**
- First run (cold cache): ~3.2 seconds
- Second run (warm cache): ~2.65 seconds
- Cache invalidation: ~2.3 seconds (rebuilds modified headers only)

**Example Cache File:**
```json
{
  "MtObject.h": {
    "hash": "21259870eb19ea1cf...",
    "file": "MtObject.h",
    "generated_at": 1760837315
  }
}
```

Do not clear caches as routine troubleshooting. Header hashes, symbol mappings,
and the dump SQLite index are deterministic local build products intended to
survive across runs. Remove only a specifically invalid artifact after its
source/schema mismatch or corruption has been identified.

### Immutable Inputs and Durable Derived Artifacts

DDON is a dead game, so the ELF and decompilation dump for build `02020005` are
immutable inputs. The common workflow is a warm fresh-process rerun, not a cold
rebuild. It is acceptable for the initial bootstrap to use substantial CPU,
memory, and disk on the reference 64 GB / Ryzen 7 7800X3D workstation when that
work produces a validated durable artifact.

Retain the compressed-dump SQLite sidecar, OS-local source-identity catalog,
symbol cache, header cache, and deterministic exports. They remain untracked
and rebuildable, but are not operationally temporary. Reuse is bound to source
SHA-256 plus producer, schema, and output-affecting configuration identities;
publication is atomic. Warm identity checks use size plus first/last 64 KiB
digests under the immutable-input contract, while `verify-source` recomputes the
full SHA-256 on demand.


## Architecture

```
src/ddon_dwarf_reconstructor/
 application/generators/     # Orchestration
 domain/
    models/dwarf/          # Data structures
    repositories/cache/     # LRU and persistent caching
    services/
        parsing/           # DWARF parsing
        generation/         # C++ generation
 infrastructure/
    config/
    logging/
 main.py
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for details.

## Platform Support

The tool automatically detects and handles different ELF platforms:

| Platform | Architecture | Endianness | DWARF Version | Detection | Output Folder | Test File |
|----------|-------------|-----------|---------------|-----------|---------------|-----------|
| **PS4** | x86-64 | Little-endian | DWARF3/4 | Automatic | `output/ps4/` | `resources/DDOORBIS.elf` |
| **PS3** | PowerPC64 | Big-endian | DWARF2 | Automatic | `output/ps3/` | `resources/PS3/EBOOT.ELF` |
| **Unknown** | Other | - | - | Fallback | `output/unknown/` | - |

Platform detection happens automatically during ELF loading. Output files are organized into platform-specific subdirectories to prevent file collisions when generating from multiple sources.

### Testing Platform Support

```bash
# Test PS4 support
uv run python main.py resources/DDOORBIS.elf --generate MtDTI,rLayout,MtFloat3

# Test PS3 support
uv run python main.py resources/PS3/EBOOT.ELF --generate MtDTI,MtUI,rLayout

# Verify output organization
ls output/ps4/        # PS4 generated headers
ls output/ps3/        # PS3 generated headers
```

### DWARF Format Differences

- **DWARF2 (PS3):** Member offsets encoded as location expressions `[DW_OP_plus_uconst, offset]`
- **DWARF3/4 (PS4):** Member offsets stored as integers directly

The location expression parser handles both formats transparently. See [dwarf_location_parser.py](src/ddon_dwarf_reconstructor/generators/utils/dwarf_location_parser.py) for implementation details.

## Development

### Quick Start

```bash
# Setup
make sync

# Run example
make run CLASS=MtObject

# Run with full hierarchy
make run-full CLASS=MtPropertyList

# Run tests
make test

# View coverage
make coverage-open
```

### Makefile Commands

**Setup:**

```bash
make sync              # Install/sync dependencies
```

**Build:**

```bash
make build-setup       # Install nuitka for native compilation
make build             # Compile to native executable (requires clang)
```

**Testing:**

```bash
make test              # Fast unit tests
make test-unit         # Unit tests only
make test-integration  # Integration tests only
make test-all          # All tests
make coverage          # Generate HTML coverage report
make coverage-open     # Generate coverage and open in browser
```

**Code Quality:**

```bash
make lint              # Run ruff linter
make format            # Format code with ruff
make format-check      # Check formatting without changes
make type-check        # Run mypy type checking
```

**Cleanup:**

```bash
make clean             # Remove transient test artifacts; preserve durable caches
make clean-all         # Remove repository build/output artifacts (not normal rerun cleanup)
```

**Agent tracing:**

```bash
make langfuse-config   # Validate the Compose configuration
make langfuse-up       # Run docker compose up -d
make langfuse-status   # Show service health and container status
make langfuse-logs     # Show recent service logs
make langfuse-stop     # Stop containers without deleting trace data
make langfuse-down     # Remove containers and network while preserving volumes
```

**Run:**

```bash
make run CLASS=MtObject                      # Generate single class
make run CLASS='MtObject,MtVector4'          # Generate multiple classes
make run-full CLASS=MtPropertyList           # Generate with full hierarchy
make run-batch FILE=resources/season2-resources.txt      # Batch process from file
make run-batch-full FILE=resources/season2-resources.txt # Batch with full hierarchy
```

**CI/CD:**

```bash
make ci                # Run full CI pipeline locally
```

**Run:**

```bash
make run CLASS=MtObject              # Quick example execution
make run-full CLASS=MtPropertyList   # Full hierarchy generation
```

### Manual Commands

```bash
# Testing
uv run pytest -m unit              # fast unit tests
uv run pytest -m integration       # slow integration tests
uv run pytest --cov=src            # with coverage

# Quality
uv run mypy src/                   # type checking
uvx ruff check src/         # linting
uvx ruff format src/        # formatting
```

### Conventions

Follow conventions in .github/copilot-instructions.md:

- Type hints required
- PEP 257 docstrings  
- 100 char line limit
- Unit tests with mocks

## Documentation

- [ARCHITECTURE.md](docs/ARCHITECTURE.md) - System design
- [TESTING.md](docs/TESTING.md) - Testing guide
- [SONARQUBE.md](docs/SONARQUBE.md) - Local SonarQube C/C++ analysis with MSVC
- [LANGFUSE_TRACING.md](docs/LANGFUSE_TRACING.md) - Local Langfuse and agent tracing setup
- [DWARF specification knowledge base](docs/knowledge-base/dwarf-specification/) - Canonical DWARF 2/3/4 JSON and Markdown artifacts
- [DWARF specification tool](tools/dwarf_spec_pipeline/) - Docker Compose rebuild and standalone `uv` checks

## Performance

| Metric | Value | Notes |
|--------|-------|-------|
| **Single class** | ~0.5-1s | With cache: <0.01s |
| **Full hierarchy (multi-file)** | ~1-3s | Resolves 74-133 classes, generates multiple files |
| **Multi-file with cache** | ~2.6s (warm) | File-based change detection, SHA256 validation |
| **Single-file mode** | ~0.9s | Legacy mode with all classes in one file |
| **Batch processing** | 4-5 symbols/min | 289 symbols in ~60 minutes |
| **Cache hit rate** | 85%+ | Typedef resolution |
| **Output size** | 130-170 KB | Complete headers with all dependencies |
| **Test suite** | ~9s | 408 non-performance tests; 394 unit tests |

### Multi-File Generation Performance (MtObject Hierarchy - PS4)

```
Total classes resolved:  74 (1 main + 73 dependencies)
Generated headers:       22 files
Total output size:       144 KB
Generation time:         ~1.06 seconds
Cache file size:         3.9 KB (.cache/DDOORBIS_headers.json)
Second run (cached):     ~2.65 seconds
```

### Multi-File Generation Performance (rLayout Hierarchy - PS3)

```
Total classes resolved:  8 (1 main + 7 dependencies)
Generated headers:       8 files
Total output size:       11.9 KB
Generation time:         ~0.92 seconds
Cache file size:         1.4 KB (.cache/EBOOT_headers.json)
```

### Batch Test Results (Season 2 - 289 Symbols)

```
Total symbols:           289
Successfully generated:  289 (100%)
Failed:                  0 (0%)
Average file size:       ~130 KB (complex), ~500 B (simple)
Classes per header:      1-133 (full definitions)
Forward declarations:    0 (all fully resolved)
```

### Example Output

**MtObject with --full-hierarchy (multi-file):**
- Input: 1 class name
- Resolved: 74 classes recursively
- Generated: 22 files, 144 KB total
- Time: ~1 second
- Cache: Automatic SHA256-based change detection

**MtObject with --full-hierarchy --single-file (legacy):**
- Input: 1 class name
- Resolved: 74 classes recursively
- Generated: 1 file, 126 KB
- Time: ~0.9 seconds


## Limitations

- **DWARF version:** Primary target DWARF 4 (PS4), limited DWARF 5 support
- **Templates:** Basic support, captures parameters but minimal syntax generation
- **Namespaces:** Limited handling, some namespace-qualified types may not resolve
- **Debug info required:** Requires .debug_info and .debug_abbrev sections
- **Stripped binaries:** Does not work with stripped binaries (no debug info)

## License

GPLv3 - See LICENSE file.

## Maintainability and regression gates

The refactored runtime keeps the public generator façades while composing
domain services through typed ports. `main.py` is a compatibility wrapper;
`ddon-dwarf-reconstructor` is the canonical entrypoint. The domain owns parsing,
definition selection, type/declarator models, hierarchy planning, and rendering
policies. Infrastructure owns pyelftools/SQLite/zstd/process adapters, and the
composition root injects those adapters.

All non-generated Python under `src/` and `tests/` is checked for modules no
larger than 400 lines, classes no larger than 250 lines, functions/methods no
larger than 75 lines, and McCabe complexity no greater than 10:

```powershell
uvx ruff check --no-fix src tests
uvx ruff format --check src tests
uv run mypy src
python scripts/quality/check_structure.py
python scripts/quality/check_boundaries.py
uv run prospector --profile .prospector.yml --tool pylint --tool pyflakes --tool mccabe src
```

The required test tiers are:

```powershell
uv run pytest -m unit -o addopts='-q --strict-markers'
uv run pytest -m "not performance" --cov=src/ddon_dwarf_reconstructor --cov-branch --cov-report=json
python scripts/quality/check_coverage.py coverage.json
```

The coverage gate is 80% total and 80% line/70% branch for parsing,
generation, orchestration, and artifact groups. Header regression manifests
record source identity, producer, configuration, cache state, file sizes, and
SHA-256 digests. The fixture baseline and real PS4 warm baseline are kept in
the external acceptance directory; generated headers, ELF files, dumps, and
caches are never committed. Use `scripts/regression/output_manifest.py` to
create or compare them.

For the documented real PS4 input, preserve the compressed dump's SQLite
sidecar between fresh processes. Use `ddon-dwarf-artifacts inspect` before
repair/rebuild and `verify-source` for an explicit full SHA-256 audit. A warm
`rLayout` run is the normal regression tier; the explicit cold sidecar rebuild
was also verified in 295.6 seconds.
