#!/usr/bin/env python3
"""
Entry point for DDON DWARF Reconstructor.

This file allows running the tool directly from the project root:
    python main.py <elf_file> --generate <symbol>
"""

import sys
from pathlib import Path

# Add src to path for development mode
project_root = Path(__file__).parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

from ddon_dwarf_reconstructor.main import main

if __name__ == "__main__":
    main()
