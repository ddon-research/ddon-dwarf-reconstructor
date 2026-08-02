"""Technology-neutral target-platform value used by application workflows."""

from enum import Enum


class ELFPlatform(Enum):
    """Supported ELF target platforms."""

    PS3 = "ps3"
    PS4 = "ps4"
    UNKNOWN = "unknown"

    def __str__(self) -> str:
        """Return the historical uppercase representation."""
        return self.value.upper()
