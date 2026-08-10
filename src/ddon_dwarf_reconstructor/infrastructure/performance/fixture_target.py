"""Deterministic child workload used by the explicit performance tier."""

from __future__ import annotations

import json
from hashlib import sha256


def main() -> int:
    """Perform bounded deterministic CPU, allocation, and serialization work."""
    values = [(index * 2654435761) % 1000003 for index in range(25_000)]
    values.sort()
    payload = json.dumps(values, separators=(",", ":")).encode("ascii")
    digest = sha256(payload).hexdigest()
    print(json.dumps({"count": len(values), "sha256": digest}, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
