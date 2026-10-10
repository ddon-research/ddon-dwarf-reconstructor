# IDA Pro PS4 Module Loader Insights

> **Archived Python project:** This page describes the frozen Python snapshot.
> Development has moved to an unpublished Rust rewrite. See [archive status](../../reference/project-status.md).

Source: [ps4_module_loader](https://github.com/SocraticBliss/ps4_module_loader/tree/657f9d380abfec9097bc4bddbc63551b3cd5e47b)
by SocraticBliss, commit `657f9d380abfec9097bc4bddbc63551b3cd5e47b`, path `ps4_module.py`;
license `GPL-3.0`. These are research/reference observations and are not treated as official
Orbis definitions.

## Key Findings

### ELF Type Detection

The IDA loader recognizes the same PS4 ELF types:

```python
ET_SCE_EXEC = 0xFE00        # Main Module
ET_SCE_REPLAY_EXEC = 0xFE01 # Replay Module
ET_SCE_RELEXEC = 0xFE04     # Relocatable PRX
ET_SCE_STUBLIB = 0xFE0C     # Stub Library
ET_SCE_DYNEXEC = 0xFE10     # Main Module - ASLR
ET_SCE_DYNAMIC = 0xFE18     # Shared Object PRX
```

### Segment Type Handling

PS4 segment types recognized:

```python
PT_SCE_DYNLIBDATA = 0x61000000   # Dynamic library data
PT_SCE_PROCPARAM = 0x61000001    # Process parameters
PT_SCE_MODULEPARAM = 0x61000002  # Research loader label; not in the SDK binutils table
PT_SCE_RELRO = 0x61000010        # Research loader label; not an official SDK definition
PT_GNU_EH_FRAME = 0x6474E550     # Exception handling frame
PT_GNU_STACK = 0x6474E551        # Stack info
PT_SCE_COMMENT = 0x6FFFFF00      # Comment
PT_SCE_LIBVERSION = 0x6FFFFF01   # Library version
PT_SCE_SEGSYM = 0x700000A8       # Segment symbols
```

### Memory Layout Strategy

The loader allows custom base address selection:

- **Original addresses**: Use addresses from ELF (may be 0)
- **0x400000**: Typical Linux/ELF base (default)
- **0x10000000**: High memory
- **0x140000000**: Very high memory

**Important**: Addresses should be page-aligned (0x1000 boundary)

### Segment Permission Mapping

Segments are classified by their permission flags:

- `EXEC | READ` (0x5) → CODE segment
- Other combinations → DATA segment

### Architecture Validation

- Only x86-64 (EM_X86_64 = 0x3E) is supported
- Rejects non-x86-64 binaries immediately

### Compiler Settings for IDA

When loading PS4 modules, the loader sets:

```python
COMP_GNU                    # GNU compiler
sizeof(bool) = 0x1         # 1 byte boolean
sizeof(long) = 0x8         # 8 byte long
sizeof(long double) = 0x10 # 16 byte long double
DEMNAM_GCC3                # Use GCC3 name demangling
```

### Segment Alignment

Recognizes these alignment values:

```python
AL_NONE = 0x0      # Absolute
AL_BYTE = 0x1      # Byte-aligned
AL_WORD = 0x2      # Word-aligned (2 bytes)
AL_DWORD = 0x4     # Dword-aligned (4 bytes)
AL_QWORD = 0x8     # Qword-aligned (8 bytes)
AL_PARA = 0x10     # Paragraph-aligned (16 bytes)
AL_4K = 0x4000     # 4K page-aligned
```

## Parsing Strategy

1. **Read ELF header** (64-byte standard header)
2. **Validate architecture** (must be x86-64)
3. **Parse program headers** at E_PHT_OFFSET
4. **Parse section headers** at E_SHT_OFFSET (if present)
5. **Apply base address** (optionally custom)
6. **Create segments** with proper permissions and alignment

## Important Considerations

1. **No Section Headers**: Like GhidraOrbis, handles ELFs without section headers
2. **Dynamic Libraries**: PRX files may have 0 base address by default
3. **ASLR Support**: ET_SCE_DYNEXEC indicates ASLR-capable main executables
4. **64-bit Only**: Rejects 32-bit ELFs immediately
5. **GNU Toolchain**: Assumes GCC-compiled code with specific ABI

## Differences from Standard ELF

The loader specifically checks for and handles:

- Custom Sony segment types (PT_SCE_*)
- Custom Sony ELF types (ET_SCE_*)
- Missing or empty section header tables
- Non-zero file addresses vs memory addresses
- Custom alignment requirements

The local official SDK source does not define `PT_SCE_RELRO`; the runtime parser therefore keeps
standard `PT_GNU_RELRO` separate from `PT_SCE_DYNLIBDATA`. The loader's base-address choices and
alignment observations are useful hypotheses only. No relocation base, NID mapping, ABI behavior,
or loader mutation is inferred by the offline evidence path.

## Integration Notes for Python Parser

Key takeaways for our Python implementation:

1. Must handle missing section headers gracefully
2. Should support custom base address relocation
3. Need to map PS4-specific segment types to meaningful names
4. Should validate x86-64 architecture
5. Must handle both absolute and relocatable modules

The repository integrates these observations only as parser fixtures and a cross-source
comparison. `artifacts validate-implementation` requires an explicit original-address or
aligned load-base policy, validates `PT_LOAD` coverage and `p_align`, and never applies IDA's
rebasing or calling-convention settings. The loader's `aerolib.csv` NID names are admissible
external candidate evidence when the local file hash and source URL/commit are retained; they
remain non-authoritative for PS4 ABI or loader behavior. The validator verifies the NID hash and
encoded library/module context where the required suffix and dynamic-table facts are available.
Unverified community names remain partial and NIDs remain opaque for promotion purposes.
