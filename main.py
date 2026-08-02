#!/usr/bin/env python3
"""
Entry point for DDON DWARF Reconstructor.

This file keeps the native-build launcher stable while the packaged Typer app owns the CLI.
"""

import sys
from pathlib import Path

# Add src to path for development mode
project_root = Path(__file__).parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

from ddon_dwarf_reconstructor.cli import app

if __name__ == "__main__":
    app()
