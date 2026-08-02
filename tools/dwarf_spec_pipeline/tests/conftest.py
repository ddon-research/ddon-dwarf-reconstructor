from __future__ import annotations

from pathlib import Path

import pytest

from dwarf_spec_pipeline.models import SourceLocation
from dwarf_spec_pipeline.source_manifest import SourceSpec

SCOPE_MARKERS = ("unit", "integration", "acceptance")
PURPOSE_MARKERS = ("functional", "regression", "non_functional")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Keep the standalone pipeline's small suite on the shared taxonomy."""
    del config
    violations: list[str] = []
    for item in items:
        scopes = [name for name in SCOPE_MARKERS if item.get_closest_marker(name)]
        purposes = [name for name in PURPOSE_MARKERS if item.get_closest_marker(name)]
        if len(scopes) == 1 and not purposes:
            item.add_marker(pytest.mark.functional)
            purposes.append("functional")
        if len(scopes) != 1:
            violations.append(f"{item.nodeid}: requires exactly one scope marker")
        if not purposes:
            violations.append(f"{item.nodeid}: requires a purpose marker")
    if violations:
        raise pytest.UsageError("Test taxonomy violations:\n" + "\n".join(violations))


@pytest.fixture
def source() -> SourceSpec:
    return SourceSpec(
        source_id="dwarf2",
        standard_version=2,
        title="DWARF Version 2",
        filename="dwarf.v2.mm",
        format="mm",
        url="https://dwarfstd.org/doc/dwarf.v2.mm",
        source_page="https://dwarfstd.org/doc/",
        sha256="0" * 64,
    )


@pytest.fixture
def source_location() -> SourceLocation:
    return SourceLocation(source_id="dwarf2", intermediate="html", block_index=7)


@pytest.fixture
def schema_path() -> Path:
    return Path(__file__).parent.parent / "schema" / "dwarf-specification.schema.json"
