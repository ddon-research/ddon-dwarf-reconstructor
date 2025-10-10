#!/bin/bash
uv add --dev nuitka
uv sync
uv run python -m nuitka --clang --onefile --jobs=16 --lto=yes --static-libpython=auto --remove-output --deployment --output-dir=build main.py

# Run via
# build/main.exe --generate "cSetInfoCoord" --full-hierarchy "D:\ddon-dwarf-reconstructor\resources\DDOORBIS.elf"
