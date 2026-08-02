"""Pytest configuration and shared fixtures."""

import csv
import sys
from pathlib import Path

import pytest

from ddon_dwarf_reconstructor.infrastructure.config import Config
from tests.support.dwarf_builders import (
    build_mock_compilation_unit,
    build_mock_die,
    build_mock_elf_file,
)
from tests.support.quality.taxonomy import (
    apply_default_functional_purpose,
    taxonomy_errors,
)

# Add src directory to path for imports
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Enforce the repository-wide scope/purpose taxonomy at collection time."""
    del config
    for item in items:
        apply_default_functional_purpose(item)

    violations = [
        f"{item.nodeid}: {', '.join(taxonomy_errors(item))}"
        for item in items
        if taxonomy_errors(item)
    ]
    if violations:
        preview = "\n".join(violations[:20])
        suffix = "" if len(violations) <= 20 else f"\n... and {len(violations) - 20} more"
        raise pytest.UsageError(f"Test taxonomy violations:\n{preview}{suffix}")


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
def sample_symbols(sample_symbols_csv: Path) -> dict[str, str | None]:
    """
    Load sample symbols from CSV file.

    Returns dict mapping symbol name to CU offset (or None if not specified).
    Note: MtObject is typically in the first CU (fast), others may be much slower.
    """
    symbols = {}
    with open(sample_symbols_csv) as f:
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


# DWARFParser fixture removed - using native pyelftools implementation


@pytest.fixture(scope="session")
def fast_symbol() -> str:
    """
    Return a symbol known to be in early CUs (fast to find).

    MtObject is the base class for most symbols, typically in first CU.
    """
    return "MtObject"


@pytest.fixture(params=["MtObject"])
def known_symbol(request: pytest.FixtureRequest, sample_symbols: dict[str, str | None]) -> str:
    """
    Parametrized fixture for testing with known symbols.

    By default only uses MtObject (fast). Tests can override with:
    @pytest.mark.parametrize("known_symbol", ["MtObject", "rLandInfo"], indirect=True)
    """
    symbol = request.param
    if symbol not in sample_symbols:
        pytest.skip(f"Symbol {symbol} not in sample CSV")
    return symbol


@pytest.fixture
def mock_elf_file():
    """Return a realistic ELF test double shared by generator tests."""
    return build_mock_elf_file()


@pytest.fixture
def mock_die():
    """Return the canonical MtObject DIE test double."""
    return build_mock_die()


@pytest.fixture
def mock_compilation_unit(mock_die):
    """Return a compilation unit containing the canonical MtObject DIE."""
    return build_mock_compilation_unit(mock_die)
