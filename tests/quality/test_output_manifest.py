from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.support.regression.output_manifest import (
    build_manifest,
    compare_manifests,
    main,
    write_manifest,
)

pytestmark = [pytest.mark.unit, pytest.mark.functional, pytest.mark.regression]


def test_manifest_hashes_selected_files_deterministically(tmp_path: Path) -> None:
    root = tmp_path / "output"
    root.mkdir()
    (root / "b.h").write_text("class B {};\n", encoding="utf-8")
    (root / "a.h").write_text("class A {};\n", encoding="utf-8")
    (root / "ignored.txt").write_text("volatile", encoding="utf-8")

    manifest = build_manifest(root)

    assert list(manifest["files"]) == ["a.h", "b.h"]
    assert manifest["files"]["a.h"]["bytes"] == len((root / "a.h").read_bytes())


def test_manifest_comparison_reports_changed_missing_and_unexpected_files() -> None:
    expected = {"files": {"a.h": {"bytes": 1, "sha256": "old"}}}
    actual = {
        "files": {
            "a.h": {"bytes": 2, "sha256": "new"},
            "b.h": {"bytes": 1, "sha256": "extra"},
        }
    }

    differences = compare_manifests(expected, actual)

    assert differences == [
        "changed output: a.h: expected {'bytes': 1, 'sha256': 'old'}, actual {'bytes': 2, 'sha256': 'new'}",
        "unexpected output: b.h",
    ]


def test_manifest_writer_is_valid_sorted_json(tmp_path: Path) -> None:
    destination = tmp_path / "baseline.json"
    write_manifest({"files": {"b.h": {}, "a.h": {}}}, destination)

    assert json.loads(destination.read_text(encoding="utf-8"))["files"] == {
        "a.h": {},
        "b.h": {},
    }


def test_create_cli_preserves_generation_command_and_configuration(tmp_path: Path) -> None:
    root = tmp_path / "output"
    root.mkdir()
    (root / "result.hpp").write_text("struct Result {};\n", encoding="utf-8")
    source = tmp_path / "input.elf"
    source.write_bytes(b"elf")
    configuration = tmp_path / "configuration.json"
    configuration.write_text('{"mode": "full-hierarchy"}\n', encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"

    assert (
        main(
            [
                "create",
                str(root),
                str(manifest_path),
                "--source",
                str(source),
                "--command",
                "uv run ddon-dwarf-reconstructor input.elf --generate Result",
                "--configuration-json",
                str(configuration),
                "--producer",
                "ddon-dwarf-reconstructor/test",
                "--cache-state",
                "warm",
            ]
        )
        == 0
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["command"].startswith("uv run ddon-dwarf-reconstructor")
    assert manifest["configuration"] == {"mode": "full-hierarchy"}
    assert manifest["cache_state"] == "warm"
