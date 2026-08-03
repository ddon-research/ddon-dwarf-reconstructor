"""Typer command-tree behavior tests."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from ddon_dwarf_reconstructor.cli import app
from ddon_dwarf_reconstructor.main import GenerationOptions

runner = CliRunner()


@pytest.mark.unit
def test_root_help_lists_unified_commands() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "generate" in result.stdout
    assert "export-knowledge" in result.stdout
    assert "artifacts" in result.stdout
    assert "performance" in result.stdout


@pytest.mark.unit
def test_version_is_available() -> None:
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == "0.1.0"


@pytest.mark.unit
def test_generate_maps_repeatable_symbols_to_typed_options(mocker, tmp_path: Path) -> None:
    elf_file = tmp_path / "input.elf"
    elf_file.write_bytes(b"fixture")
    run_generation = mocker.patch("ddon_dwarf_reconstructor.cli.run_generation", return_value=0)

    result = runner.invoke(
        app,
        [
            "generate",
            str(elf_file),
            "--symbol",
            "A",
            "--symbol",
            "B",
            "--full-hierarchy",
            "--exhaustive",
        ],
    )

    assert result.exit_code == 0
    options = run_generation.call_args.args[0]
    assert isinstance(options, GenerationOptions)
    assert options.symbols == ("A", "B")
    assert options.full_hierarchy is True
    assert options.exhaustive is True


@pytest.mark.unit
def test_generate_rejects_symbols_file_and_symbol_options(tmp_path: Path) -> None:
    elf_file = tmp_path / "input.elf"
    elf_file.write_bytes(b"fixture")
    symbols_file = tmp_path / "symbols.txt"
    symbols_file.write_text("A\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "generate",
            str(elf_file),
            "--symbol",
            "A",
            "--symbols-file",
            str(symbols_file),
        ],
    )

    assert result.exit_code == 1
    assert "both --symbol and --symbols-file" in result.stdout + result.stderr


@pytest.mark.unit
def test_export_knowledge_requires_output_dir_and_uses_unified_command(mocker) -> None:
    run_generation = mocker.patch("ddon_dwarf_reconstructor.cli.run_generation", return_value=0)

    result = runner.invoke(
        app,
        [
            "export-knowledge",
            "input.elf",
            "--output-dir",
            "output/knowledge",
            "--symbol",
            "A",
            "--build-id",
            "build-1",
        ],
    )

    assert result.exit_code == 0
    options = run_generation.call_args.args[0]
    assert options.export_knowledge == Path("output/knowledge")
    assert options.build_id == "build-1"


@pytest.mark.unit
def test_export_knowledge_maps_repeatable_tool_evidence(mocker) -> None:
    run_generation = mocker.patch("ddon_dwarf_reconstructor.cli.run_generation", return_value=0)

    result = runner.invoke(
        app,
        [
            "export-knowledge",
            "input.elf",
            "--output-dir",
            "output/knowledge",
            "--symbol",
            "A",
            "--tool-evidence",
            "exports/orbis.json",
            "--tool-evidence",
            "exports/llvm.json",
        ],
    )

    assert result.exit_code == 0
    options = run_generation.call_args.args[0]
    assert options.tool_export_manifests == (
        Path("exports/orbis.json"),
        Path("exports/llvm.json"),
    )
