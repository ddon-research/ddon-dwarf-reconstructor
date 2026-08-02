from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.acceptance,
    pytest.mark.functional,
    pytest.mark.regression,
    pytest.mark.real_artifact,
    pytest.mark.official,
]


def test_official_artifacts_have_expected_coverage() -> None:
    if os.environ.get("DWARF_SPEC_OFFICIAL") != "1":
        pytest.skip("set DWARF_SPEC_OFFICIAL=1 after the Docker Compose build")

    generated = (
        Path(__file__).parents[3] / "docs" / "knowledge-base" / "dwarf-specification" / "generated"
    )
    required_tokens = {
        "DW_TAG_compile_unit",
        "DW_AT_name",
        "DW_FORM_addr",
        "DW_OP_plus_uconst",
        "DW_LANG_C_plus_plus",
    }
    forbidden_tokens = ("lf(CW)", "box expand", "<img", "<span", "\\!.ix")
    for version in (2, 3, 4):
        json_path = generated / f"dwarf{version}.json"
        markdown_path = generated / f"dwarf{version}.md"
        document = json.loads(json_path.read_text(encoding="utf-8"))
        serialized = json_path.read_text(encoding="utf-8") + markdown_path.read_text(
            encoding="utf-8"
        )
        assert document["specification"]["version"] == version
        assert document["statistics"]["section_count"] >= 100
        assert required_tokens <= set(constant["name"] for constant in document["constants"]) | {
            token for token in required_tokens if token in serialized
        }
        assert not any(token in serialized for token in forbidden_tokens)
