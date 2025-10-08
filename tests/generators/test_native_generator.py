"""Test the native pyelftools-based generator."""

import os
from pathlib import Path

from ddon_dwarf_reconstructor.generators.native_generator import NativeDwarfGenerator

def test_native_generator():
    """Test generating MtObject header using native pyelftools."""
    # Path to the DWARF data file
    dwarf_path = Path("d:/ddon-dwarf-reconstructor/resources/DDOORBIS.elf")
    
    if not dwarf_path.exists():
        print(f"DWARF file not found: {dwarf_path}")
        return
    
    print("Testing native pyelftools generator...")
    
    # Use context manager to ensure proper cleanup
    with NativeDwarfGenerator(dwarf_path) as generator:
        # Generate MtObject header
        header_content = generator.generate_header("MtObject")
        
        # Write to output file
        output_path = Path("d:/ddon-dwarf-reconstructor/output/MtObject_native.h")
        output_path.parent.mkdir(exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(header_content)
            
        print(f"Generated header written to: {output_path}")
        print(f"Header length: {len(header_content)} characters")
        
        # Print first few lines for verification
        lines = header_content.split('\n')[:10]
        print("First 10 lines:")
        for i, line in enumerate(lines, 1):
            print(f"{i:2}: {line}")

if __name__ == "__main__":
    test_native_generator()