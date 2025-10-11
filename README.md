# DDON DWARF Reconstructor

Reconstructs C++ class definitions from DWARF debug information in ELF files. Developed for Dragon's Dogma Online modding.

## Features

- Extracts member variables, methods, virtual tables, inheritance hierarchies
- Type resolution with typedef chains
- Memory layout and packing analysis
- PS4 ELF support with automatic section patching
- Domain-driven architecture: 92 tests, 48% coverage

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
# Single class
uv run python main.py resources/DDOORBIS.elf --generate MtObject

# Full inheritance hierarchy
uv run python main.py resources/DDOORBIS.elf --generate ClassName --full-hierarchy

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

| Operation | Time | Notes |
|-----------|------|-------|
| Single class | ~1s | 3-5x faster than original |
| Full hierarchy | ~3s | Includes all base classes |
| Cached lookup | <0.01s | Persistent cache |

## Limitations

- DWARF 4 primary target (PS4), limited DWARF 5 support
- Basic template support, minimal namespace handling
- Requires .debug_info and .debug_abbrev sections
- Does not work with stripped binaries

## Comparison

| Tool | Purpose | DWARF | Output |
|------|---------|-------|--------|
| ddon-dwarf-reconstructor | C++ headers | DWARF 4 | C++ |
| dwarfdump | DWARF inspection | Full | Text |
| pahole | Struct layout | Limited | Text |
| IDA Pro / Ghidra | Binary analysis | Basic | Pseudocode |

## License

GPLv3 - See LICENSE file.
