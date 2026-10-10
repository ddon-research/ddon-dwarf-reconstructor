"""Include guards remain legal and distinct for C++ identities."""

import re

import pytest
from hypothesis import given
from hypothesis import strategies as st

from ddon_dwarf_reconstructor.domain.services.generation.header_guards import header_guard

pytestmark = [pytest.mark.unit, pytest.mark.regression]


@given(st.text())
def test_header_guard_is_a_bounded_nonreserved_cpp_identifier(name: str) -> None:
    guard = header_guard(name)
    assert re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", guard)
    assert not guard.startswith("_")
    assert len(guard) <= 104
    assert guard == header_guard(name)


@pytest.mark.parametrize(
    "left,right",
    [
        ("Box<-1>", "Box<1>"),
        ("a::Box", "a_Box"),
        ("Item", "item"),
        ("left::Box<int>", "right::Box<int>"),
        ("X" * 220 + "A", "X" * 220 + "B"),
    ],
)
def test_filename_or_uppercase_collisions_do_not_merge_guard_identity(
    left: str, right: str
) -> None:
    assert header_guard(left) != header_guard(right)


def test_invalid_guard_suffix_is_rejected() -> None:
    with pytest.raises(ValueError, match="invalid header guard suffix"):
        header_guard("Box", "-invalid")
