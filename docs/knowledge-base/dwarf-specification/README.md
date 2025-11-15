# DWARF Specification Files

Official DWARF debugging format specifications.

## Contents

### DWARF 2 (1993)
- **DWARF2.pdf** (268.6 KB) - Official DWARF 2.0.0 specification
- **DWARF2.mm.txt** (230.3 KB) - Text extraction from DWARF2 specification

**Used by:** PS3 (PowerPC64, big-endian)

**Key features:**
- Basic type information and structure layout
- Location expressions for member offsets (DW_OP_plus_uconst)
- Compilation unit structure
- DIE (Debug Information Entry) format

### DWARF 4 (2010)
- **DWARF4.pdf** (2671.7 KB) - Official DWARF 4 specification
- **DWARF4.docx** - DWARF 4 specification in Word format
- **DWARF4.txt** (505.2 KB) - Text extraction from DWARF4 specification

**Used by:** PS4 (x86-64, little-endian)

**Key features:**
- Enhanced type system with templates
- Improved location expressions
- Better namespace support
- Signature-based type references

## Usage in Project

### DWARF 2 Support
The tool parses DWARF2 format for PS3 ELF files:
- Location expressions: `[DW_OP_plus_uconst, offset]` format
- Platform detection: EM_PPC64, big-endian
- Test file: `resources/PS3/EBOOT.ELF`

See: [PS3_DWARF2_LOCATION_EXPRESSIONS.md](../../PS3_DWARF2_LOCATION_EXPRESSIONS.md)

### DWARF 4 Support
Primary target format for PS4 ELF files:
- Standard attribute parsing
- Direct offset integers (not location expressions)
- Platform detection: EM_X86_64, little-endian, type 0xfe10
- Test file: `resources/DDOORBIS.elf`

See: [DWARF_TAG_ANALYSIS.md](../../DWARF_TAG_ANALYSIS.md)

## Key Differences

| Feature | DWARF 2 | DWARF 4 |
|---------|---------|---------|
| Location expressions | Required for offsets | Direct integers |
| Template support | Limited | Full support |
| Namespace handling | Basic | Enhanced |
| Type signatures | Not available | Available |
| File size | Smaller | Larger (more metadata) |

## References

- [DWARF Standards Committee](http://dwarfstd.org/)
- [DWARF 4 Standard Online](http://dwarfstd.org/doc/DWARF4.pdf)
- [DWARF 2 Standard Online](http://dwarfstd.org/Dwarf2_Doc.pdf)

## Related Documentation

- [ARCHITECTURE.md](../../ARCHITECTURE.md) - Platform detection and DWARF parsing
- [PS3_DWARF2_LOCATION_EXPRESSIONS.md](../../PS3_DWARF2_LOCATION_EXPRESSIONS.md) - PS3-specific parsing
- [knowledge-base/dwarf/](../dwarf/) - DWARF parsing patterns from other projects
