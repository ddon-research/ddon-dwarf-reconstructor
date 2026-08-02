from __future__ import annotations

from pathlib import Path

from tests.support.quality.check_structure import MAX_CLASS_LINES, check, inspect_file


def test_structure_checker_accepts_small_module(tmp_path: Path) -> None:
    source = tmp_path / "small.py"
    source.write_text(
        "def add(left: int, right: int) -> int:\n    return left + right\n", encoding="utf-8"
    )

    assert inspect_file(source) == []


def test_structure_checker_accepts_functionally_busy_class_budget(tmp_path: Path) -> None:
    source = tmp_path / "busy_class.py"
    source.write_text("class BusyClass:\n" + "    pass\n" * (MAX_CLASS_LINES - 1), encoding="utf-8")

    assert inspect_file(source) == []


def test_structure_checker_reports_module_class_function_and_complexity(tmp_path: Path) -> None:
    source = tmp_path / "large.py"
    source.write_text(
        "class Example:\n"
        + "    def method(self, value: int) -> int:\n"
        + "        result = value\n"
        + "        if value > 0:\n"
        + "            result += 1\n"
        + "        return result\n"
        + "\n"
        + "def complicated(value: int) -> int:\n"
        + "    result = value\n"
        + "    if value > 0:\n        result += 1\n"
        + "    if value > 1:\n        result += 1\n"
        + "    if value > 2:\n        result += 1\n"
        + "    if value > 3:\n        result += 1\n"
        + "    if value > 4:\n        result += 1\n"
        + "    if value > 5:\n        result += 1\n"
        + "    if value > 6:\n        result += 1\n"
        + "    if value > 7:\n        result += 1\n"
        + "    if value > 8:\n        result += 1\n"
        + "    if value > 9:\n        result += 1\n"
        + "    return result\n",
        encoding="utf-8",
    )

    violations = inspect_file(source)
    assert any(item.kind == "cyclomatic complexity" for item in violations)


def test_check_uses_only_python_files(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("not Python", encoding="utf-8")
    source = tmp_path / "small.py"
    source.write_text("value = 1\n", encoding="utf-8")

    assert check([tmp_path]) == []
