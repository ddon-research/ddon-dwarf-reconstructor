"""Pytest configuration and shared fixtures."""

import csv
import sys
from pathlib import Path
from typing import Generator, Optional

import pytest

# Add src directory to path for imports
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from ddon_dwarf_reconstructor.config import Config
from ddon_dwarf_reconstructor.core import DWARFParser


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Return the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture(scope="session")
def sample_symbols_csv(project_root: Path) -> Path:
    """Return path to sample symbols CSV file."""
    csv_path = project_root / "resources" / "sample-symbols.csv"
    if not csv_path.exists():
        pytest.skip(f"Sample symbols CSV not found at {csv_path}")
    return csv_path


@pytest.fixture(scope="session")
def sample_symbols(sample_symbols_csv: Path) -> dict[str, Optional[str]]:
    """
    Load sample symbols from CSV file.

    Returns dict mapping symbol name to CU offset (or None if not specified).
    Note: MtObject is typically in the first CU (fast), others may be much slower.
    """
    symbols = {}
    with open(sample_symbols_csv, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row["name"].strip()
            offset = row["cu_offset"].strip() if row["cu_offset"].strip() else None
            symbols[name] = offset

    if not symbols:
        pytest.skip("No symbols found in sample CSV")

    return symbols


@pytest.fixture(scope="session")
def config() -> Config:
    """Load configuration from environment."""
    return Config.from_env()


@pytest.fixture(scope="session")
def elf_file_path(config: Config) -> Path:
    """
    Return path to ELF file, skipping test if not available.
    """
    if not config.elf_file_path.exists():
        pytest.skip(f"ELF file not found at {config.elf_file_path}")
    return config.elf_file_path


@pytest.fixture(scope="function")
def elf_parser(elf_file_path: Path) -> Generator[DWARFParser, None, None]:
    """
    Create a DWARFParser instance for testing.

    Uses function scope so each test gets a fresh parser.
    """
    with DWARFParser(elf_file_path, verbose=False) as parser:
        yield parser


@pytest.fixture(scope="session")
def fast_symbol() -> str:
    """
    Return a symbol known to be in early CUs (fast to find).

    MtObject is the base class for most symbols, typically in first CU.
    """
    return "MtObject"


@pytest.fixture(params=["MtObject"])
def known_symbol(request: pytest.FixtureRequest, sample_symbols: dict[str, Optional[str]]) -> str:
    """
    Parametrized fixture for testing with known symbols.

    By default only uses MtObject (fast). Tests can override with:
    @pytest.mark.parametrize("known_symbol", ["MtObject", "rLandInfo"], indirect=True)
    """
    symbol = request.param
    if symbol not in sample_symbols:
        pytest.skip(f"Symbol {symbol} not in sample CSV")
    return symbol
