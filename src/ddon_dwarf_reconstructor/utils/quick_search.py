"""Quick search functionality that doesn't build full DIE trees."""

from pathlib import Path

from elftools.elf.elffile import ELFFile

from .elf_patches import patch_pyelftools_for_ps4

# Apply PS4 ELF patches
patch_pyelftools_for_ps4()


def quick_search_by_name(elf_path: Path, search_name: str, verbose: bool = False) -> bool:
    """
    Quickly search for a DIE by name without building full tree structures.

    This is much faster for large ELF files as it doesn't parse all children.

    Args:
        elf_path: Path to the ELF file
        search_name: Name to search for (DW_AT_name value)
        verbose: Enable verbose output

    Returns:
        True if found, False otherwise
    """
    patch_pyelftools_for_ps4()

    with open(elf_path, "rb") as f:
        elffile = ELFFile(f, stream_loader=None)

        if verbose:
            print(f"Opened ELF file: {elf_path}")
            print(f"Architecture: {elffile.get_machine_arch()}")

        dwarf_info = elffile.get_dwarf_info()

        if not dwarf_info:
            if verbose:
                print("No DWARF information found")
            return False

        if verbose:
            print(f"DWARF version: {dwarf_info.config.default_address_size * 8}-bit")
            print(f"\nSearching for '{search_name}'...\n")

        cu_count = 0
        for cu in dwarf_info.iter_CUs():
            cu_count += 1

            if verbose and cu_count % 10 == 0:
                print(f"  Searched {cu_count} compilation units...")

            # Iterate through all DIEs in this CU without building trees
            for die in cu.iter_DIEs():
                # Check if this DIE has a name attribute matching our search
                if "DW_AT_name" in die.attributes:
                    name_attr = die.attributes["DW_AT_name"]
                    name_value = name_attr.value

                    # Handle both bytes and string
                    if isinstance(name_value, bytes):
                        name_value = name_value.decode("utf-8", errors="ignore")
                    else:
                        name_value = str(name_value)

                    if name_value == search_name:
                        # Found it!
                        print(f"\n✓ Found '{search_name}'!")
                        print(f"  Compilation Unit: offset 0x{cu.cu_offset:08x}")
                        print(f"  DIE offset: 0x{die.offset:08x}")
                        print(f"  DIE tag: {die.tag}")

                        # Print some attributes
                        if "DW_AT_byte_size" in die.attributes:
                            byte_size = die.attributes["DW_AT_byte_size"].value
                            print(f"  Size: {byte_size} bytes")

                        if "DW_AT_decl_file" in die.attributes:
                            decl_file = die.attributes["DW_AT_decl_file"].value
                            if isinstance(decl_file, bytes):
                                decl_file = decl_file.decode("utf-8", errors="ignore")
                            print(f"  Declared in: {decl_file}")

                        return True

        if verbose:
            print(f"\n✗ '{search_name}' not found (searched {cu_count} compilation units)")

        return False