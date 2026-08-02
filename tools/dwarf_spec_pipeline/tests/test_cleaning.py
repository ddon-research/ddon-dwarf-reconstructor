from __future__ import annotations

import pytest

from dwarf_spec_pipeline.cleaning import clean_converter_text


@pytest.mark.unit
def test_converter_cleanup_does_not_remove_real_words() -> None:
    assert clean_converter_text("entries. The next section") == "entries. The next section"
    assert clean_converter_text("box expand center tab(;);") == ""
    assert clean_converter_text(r"\!.ix \$1 \$2\n\$3 \$4") == ""
