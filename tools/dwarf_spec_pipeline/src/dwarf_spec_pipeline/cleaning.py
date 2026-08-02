"""Shared cleanup for converter control text while preserving document prose."""

from __future__ import annotations

import re


def clean_converter_text(text: str) -> str:
    text = text.replace("\xa0", " ").replace("\u00ad", "")
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\\!?\.ix\b.*", "", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"(?:lf\(CW\)|lf\(R\)|lfB)", "", text)
    text = re.sub(
        r"(?:box\s+expand\s+center|box\s+center\s+expand|center\s+box)"
        r"\s+tab\([^)]*\)\s*;?",
        "",
        text,
    )
    text = re.sub(
        r"(?:box\s+(?:center|expand)|center\s+box|center|box)\s*;(?=\s|$)",
        "",
        text,
    )
    text = re.sub(r"(?<![A-Za-z0-9])(?:;\s*)?(?:[ls](?:\s+[ls])*)\.\s*", "", text)
    text = re.sub(r";\s*l(?:\s+l)+\s*$", "", text)
    text = re.sub(r"\\\s*$", "", text)
    text = re.sub(r"[ \t\r\n]+", " ", text).strip()
    text = re.sub(r"\bU\s+NIX\b", "UNIX", text)
    text = re.sub(r"(?<=[a-z])(?=[A-Z][a-z])", " ", text)
    text = re.sub(r"(?<=[A-Za-z0-9])(?=DWARF\b)", " ", text)
    text = re.sub(r"(?<=[A-Za-z0-9])(?=DW_[A-Z])", " ", text)
    return "" if re.fullmatch(r"_+", text) else text
