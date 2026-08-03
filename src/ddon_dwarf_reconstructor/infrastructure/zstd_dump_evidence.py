"""Streaming producer/version evidence for LLVM text DWARF dumps."""

from __future__ import annotations

import compression.zstd as zstd
import re
from collections import Counter
from pathlib import Path
from typing import Any

_CU_RE = re.compile(
    r"^(0x[0-9a-f]+):\s+Compile Unit:.*?version\s*=\s*(?:0x)?([0-9a-f]+)",
    re.IGNORECASE,
)
_PRODUCER_RE = re.compile(r'DW_AT_producer.*?["\']([^"\']+)["\']')


def inspect_dump(path: Path) -> dict[str, Any]:
    """Stream one compressed dump and summarize CU versions and producers."""
    versions: Counter[str] = Counter()
    producers: Counter[str] = Counter()
    cu_count = 0
    with zstd.open(str(path), "rt", encoding="utf-8", errors="replace") as stream:
        for raw_line in stream:
            line = raw_line.rstrip("\r\n")
            header_match = _CU_RE.match(line)
            if header_match is not None:
                cu_count += 1
                versions[str(int(header_match.group(2), 16))] += 1
                continue
            producer_match = _PRODUCER_RE.search(line)
            if producer_match is not None:
                producers[producer_match.group(1)] += 1
    return {
        "path": str(path.resolve()),
        "cu_count": cu_count,
        "versions": dict(sorted(versions.items(), key=lambda item: int(item[0]))),
        "version_consistent": len(versions) <= 1,
        "producers": dict(sorted(producers.items())),
    }
