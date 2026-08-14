"""External performance-artifact path policy."""

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from ddon_dwarf_reconstructor.infrastructure.performance import paths

pytestmark = [pytest.mark.unit, pytest.mark.functional]


def test_windows_default_performance_artifacts_use_temp_volume(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The default raw-profiler root does not fall back to durable app data."""
    # Do not mutate the process-wide ``os`` module: pathlib.Path consults
    # ``os.name`` when it is instantiated, which would make this Linux test
    # try to construct an unsupported WindowsPath.
    monkeypatch.setattr(paths, "os", SimpleNamespace(name="nt", environ=os.environ))
    monkeypatch.setenv("TEMP", str(tmp_path / "temp"))
    monkeypatch.setenv("TMP", str(tmp_path / "tmp"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local-app-data"))
    monkeypatch.delenv("DDON_PERFORMANCE_ARTIFACT_DIR", raising=False)

    assert paths.get_performance_artifact_dir() == (
        tmp_path / "temp" / "ddon-dwarf-reconstructor" / "performance"
    )


def test_explicit_performance_artifact_root_wins(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An explicit evidence root remains the escape hatch for CI or experiments."""
    configured = tmp_path / "explicit"
    monkeypatch.setenv("DDON_PERFORMANCE_ARTIFACT_DIR", str(configured))

    assert paths.get_performance_artifact_dir() == configured.resolve()
