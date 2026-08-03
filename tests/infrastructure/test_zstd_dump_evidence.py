from io import StringIO
from unittest.mock import patch

import pytest

from ddon_dwarf_reconstructor.infrastructure.zstd_dump_evidence import inspect_dump


@pytest.mark.unit
@pytest.mark.regression
def test_compressed_dump_evidence_counts_versions_and_producers(tmp_path) -> None:  # type: ignore[no-untyped-def]
    dump = tmp_path / "dump.zst"
    dump.touch()
    text = """\
0x0000: Compile Unit: length = 0x10, format = DWARF32, version = 0x0004
    DW_AT_producer [DW_FORM_strp] (\"clang ps4\")
0x0010: Compile Unit: length = 0x10, format = DWARF32, version = 0x0004
    DW_AT_producer [DW_FORM_strp] (\"clang ps4\")
"""
    with patch("compression.zstd.open") as open_zstd:
        open_zstd.return_value.__enter__.return_value = StringIO(text)
        evidence = inspect_dump(dump)

    assert evidence["cu_count"] == 2
    assert evidence["versions"] == {"4": 2}
    assert evidence["version_consistent"] is True
    assert evidence["producers"] == {"clang ps4": 2}
