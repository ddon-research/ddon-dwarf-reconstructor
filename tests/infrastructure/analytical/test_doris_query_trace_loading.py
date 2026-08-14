"""Query-trace artifact loading status tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from ddon_dwarf_reconstructor.infrastructure.analytical.benchmark.doris import (
    current_generation as generation_module,
)

pytestmark = [pytest.mark.unit, pytest.mark.functional]


def test_generation_query_trace_loading_distinguishes_missing_invalid_and_non_object(
    tmp_path: Path,
) -> None:
    missing = generation_module._load_query_trace(tmp_path / "missing.json")
    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text("not-json", encoding="utf-8")
    invalid = generation_module._load_query_trace(invalid_path)
    list_path = tmp_path / "list.json"
    list_path.write_text("[]", encoding="utf-8")
    non_object = generation_module._load_query_trace(list_path)
    assert missing["status"] == "not_observed"
    assert invalid["status"] == "partial"
    assert non_object["status"] == "partial"
