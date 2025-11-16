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
- **High performance:** Persistent caching, offset-based resolution, CU size-sorted scanning, timeout protection (600s default)
- **Robust architecture:** Domain-driven design, 216 unit tests, type-safe

## Requirements

- Python 3.13+
- ELF file with DWARF debug information

## Installation

```bash
uv sync
uv run pytest -m unit  # verify
```

## Usage

### Python Script

```bash
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
- Default mode (cache hit): <1 second
- Exhaustive mode (full scan): ~60 minutes (all CUs)
- **Exhaustive with dump:** ~10 minutes (precomputed index)

**Usage:**
```bash
# Standard exhaustive (slow but thorough)
uv run python main.py resources/DDOORBIS.elf --generate rLayout --exhaustive

# Fast exhaustive with compressed dump file
uv run python main.py resources/DDOORBIS.elf --generate rLayout --exhaustive \
  --dwarf-dump /path/to/llvm-dwarfdump-output.zst
```

**Cache Behavior:**
- Exhaustive search **populates the cache** with the best definition found
- Subsequent runs use cached offset for instant lookups (<1s)
- Cache asymptotically covers all regular use cases
- Cache file: `resources/.cache/{elf_name}_dwarf_cache.json`

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
--dwarf-dump PATH     # path to compressed llvm-dwarfdump output (.zst) for fast exhaustive search
```

### Caching System

The project uses two caching mechanisms for optimal performance:

#### 1. Symbol Cache (DWARF Offset Cache)

**Location:** `resources/.cache/{elf_name}_dwarf_cache.json`

**Purpose:** Caches symbol→CU/DIE offset mappings with multi-definition support

**Cache Format:** v3.0 (auto-migrates from v1.0/v2.0)

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
- Cache hit: <1 second (instant DIE retrieval)
- Cache miss + exhaustive: ~10 minutes (with dump), then cached
- Cache miss + default: ~1-5 seconds (targeted search), then cached

**Cache Repair (No Need to Regenerate!):**
```bash
# If cache corruption detected, automatic repair attempts:
# 1. Fix missing fields (migrates v1.0/v2.0 → v3.0)
# 2. Remove duplicate definitions
# 3. Fix inconsistent mappings
# 4. Remove orphaned entries

# Manual validation/repair (coming soon):
# uv run python main.py --validate-cache resources/DDOORBIS.elf
```

**Example:**
```bash
# First run (exhaustive): ~10 minutes, populates cache with ALL definitions
uv run python main.py --generate rLayout --exhaustive --dwarf-dump dump.zst resources/DDOORBIS.elf

# Second run (any mode): <1 second via cache (uses best definition)
uv run python main.py --generate rLayout resources/DDOORBIS.elf
```

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

To clear cache: `rm .cache/*.json`


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
make clean             # Remove test artifacts and cache
make clean-all         # Remove all generated files
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
uv run ruff check src/             # linting
uv run ruff format src/            # formatting
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
| **Test suite** | 0.24s | 196 unit tests |

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
