# DDON DWARF Reconstructor

Reconstructs C++ class definitions from DWARF debug information in ELF files. Developed for Dragon's Dogma Online modding.

## Features

- **Complete dependency resolution:** Recursively resolves all type dependencies
- **Full class definitions:** Generates complete headers with all dependent classes (not just forward declarations)
- **Inheritance hierarchies:** Complete base-to-derived chains with automatic ordering
- **Type resolution:** Handles typedefs, pointers, references, arrays
- **Memory layout analysis:** Packing suggestions and padding detection
- **Platform support:** PS4 (x86-64, DWARF3/4) and PS3 (PowerPC64, DWARF2) with automatic detection
- **Output organization:** Platform-specific output folders (output/ps4/, output/ps3/)
- **PS4 ELF support:** Automatic section patching for PS4 binaries
- **High performance:** Persistent caching, offset-based resolution
- **Robust architecture:** Domain-driven design, 155+ unit tests, type-safe

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

# Full inheritance hierarchy (PS4)
uv run python main.py resources/DDOORBIS.elf --generate ClassName --full-hierarchy

# PS3 single class
uv run python main.py resources/PS3/EBOOT.ELF --generate MtDTI

# PS3 multiple classes
uv run python main.py resources/PS3/EBOOT.ELF --generate MtUI,rLayout

# Batch processing from file (PS4, one symbol per line)
uv run python main.py resources/DDOORBIS.elf --symbols-file resources/season2-resources.txt

# Batch processing with full hierarchy (289 symbols validated, PS4)
````
uv run python main.py resources/DDOORBIS.elf --symbols-file resources/season2-resources.txt --full-hierarchy

# With options
uv run python main.py resources/DDOORBIS.elf --generate ClassName --output dir/ --verbose
```

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
--full-hierarchy      # include all base classes
--generate SYMBOL     # generate for single or multiple symbols (comma-separated)
--symbols-file FILE   # read symbols from file (one per line, alternative to --generate)
```

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
| **Full hierarchy** | ~1-3s | Resolves 74-133 classes recursively |
| **Batch processing** | 4-5 symbols/min | 289 symbols in ~60 minutes |
| **Cache hit rate** | 85%+ | Typedef resolution |
| **Output size** | 130-170 KB | Complete headers with all dependencies |
| **Test suite** | 0.24s | 120 unit tests |

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

**MtObject with --full-hierarchy:**
- Input: 1 class name
- Resolved: 74 classes recursively
- Generated: 3,605 lines, 126 KB
- Forward declarations: 0
- Time: ~2 seconds

## Limitations

- **DWARF version:** Primary target DWARF 4 (PS4), limited DWARF 5 support
- **Templates:** Basic support, captures parameters but minimal syntax generation
- **Namespaces:** Limited handling, some namespace-qualified types may not resolve
- **Debug info required:** Requires .debug_info and .debug_abbrev sections
- **Stripped binaries:** Does not work with stripped binaries (no debug info)

## License

GPLv3 - See LICENSE file.
