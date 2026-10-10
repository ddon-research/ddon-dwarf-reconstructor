"""Stable preprocessor identities independent of filesystem naming rules."""

import re

from ....core.content_hash import sha256_text


def header_guard(name: str, suffix: str = "_H") -> str:
    """Keep a readable stem and distinguish scopes, punctuation and letter case."""
    if re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", suffix) is None:
        raise ValueError(f"invalid header guard suffix: {suffix!r}")
    stem = re.sub(r"[^A-Za-z_0-9]+", "_", name).strip("_")[:80].upper() or "UNNAMED"
    digest = sha256_text(name)[:16].upper()
    return f"DDON_{stem}_{digest}{suffix}"
