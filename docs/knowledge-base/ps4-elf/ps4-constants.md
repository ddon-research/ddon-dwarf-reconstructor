# PS4 ELF Constants and Extensions

Sources: [GhidraOrbis](https://github.com/astrelsky/GhidraOrbis/tree/2d6e3fac23ae9830e941c32826e97100ed603311) at commit
`2d6e3fac23ae9830e941c32826e97100ed603311` for research comparison and the
local official Orbis binutils source package `binutils-orbis-2_22_1-src-SDK6500-n267` for the
runtime definition subset.

## ELF Types (e_type values)

PS4 uses custom ELF types in the SCE (Sony Computer Entertainment) range:

```java
ET_SCE_EXEC = 0xFE00          // Executable
ET_SCE_REPLAY_EXEC = 0xFE01   // Replay executable
ET_SCE_RELEXEC = 0xFE04       // Relocatable executable
ET_SCE_STUBLIB = 0xFE0C       // Stub library
ET_SCE_DYNEXEC = 0xFE10       // Dynamic executable
ET_SCE_DYNAMIC = 0xFE18       // Dynamic library (PRX)
ET_SCE_KERNEL = 2             // Kernel module
```

## Program Header Types (p_type values)

PS4 defines custom program segment types:

```java
PT_SCE_DYNLIBDATA = 0x61000000     // Dynamic library data
PT_SCE_PROCPARAM = 0x61000001      // Process parameters
PT_SCE_COMMENT = 0x6FFFFF00        // Comment
PT_SCE_LIBVERSION = 0x6FFFFF01     // Library version
PT_GNU_RELRO = 0x6474E552           // Standard GNU read-only-after-relocation segment
```

The official SDK source defines the four `PT_SCE_*` values above and standard `PT_GNU_RELRO`.
It does not define `PT_SCE_RELRO`; the latter, along with `PT_SCE_RELA`,
`PT_SCE_MODULEPARAM`, and `PT_SCE_SEGSYM`, remains a Ghidra/loader research label rather than a
runtime parser definition in this project.

## Dynamic Section Tags (d_tag values)

PS4 extends the dynamic section with many SCE-specific tags:

### Module Information

```java
DT_SCE_MODULE_INFO = 0x6100000D         // Module information
DT_SCE_MODULE_ATTR = 0x61000011         // Module attributes
DT_SCE_NEEDED_MODULE = 0x6100000F       // Required module dependency
DT_SCE_FINGERPRINT = 0x61000007         // Module fingerprint
DT_SCE_ORIGINAL_FILENAME = 0x61000009   // Original filename
```

### Library Management

```java
DT_SCE_EXPORT_LIB = 0x61000013          // Export library
DT_SCE_IMPORT_LIB = 0x61000015          // Import library
DT_SCE_EXPORT_LIB_ATTR = 0x61000017     // Export library attributes
DT_SCE_IMPORT_LIB_ATTR = 0x61000019     // Import library attributes
DT_SCE_STUB_MODULE_NAME = 0x6100001D    // Stub module name
DT_SCE_STUB_MODULE_VERSION = 0x6100001F // Stub module version
DT_SCE_STUB_LIBRARY_NAME = 0x61000021   // Stub library name
DT_SCE_STUB_LIBRARY_VERSION = 0x61000023// Stub library version
```

### Symbol and String Tables

```java
DT_SCE_STRTAB = 0x61000035      // SCE string table address
DT_SCE_STRSZ = 0x61000037       // SCE string table size
DT_SCE_SYMTAB = 0x61000039      // SCE symbol table address
DT_SCE_SYMENT = 0x6100003B      // SCE symbol table entry size
DT_SCE_SYMTABSZ = 0x6100003F    // SCE symbol table size
```

### Relocations

```java
DT_SCE_RELA = 0x6100002F        // SCE relocation table address
DT_SCE_RELASZ = 0x61000031      // SCE relocation table size
DT_SCE_RELAENT = 0x61000033     // SCE relocation entry size
DT_SCE_JMPREL = 0x61000029      // SCE jump relocation table
DT_SCE_PLTREL = 0x6100002B      // SCE PLT relocation type
DT_SCE_PLTRELSZ = 0x6100002D    // SCE PLT relocation size
DT_SCE_PLTGOT = 0x61000027      // SCE PLT/GOT address
```

### Hash Table

```java
DT_SCE_HASH = 0x61000025        // SCE hash table
DT_SCE_HASHSZ = 0x6100003D      // SCE hash table size
```

### Other

```java
DT_SCE_IDTABENTSZ = 0x61000005  // ID table entry size
DT_SCE_HIOS = 0x6FFFF000        // High OS-specific value
```

The complete useful SDK table is preserved in the typed `orbis_sdk_definitions` module, including
the import/export, stub, hash, relocation, string, symbol, and fingerprint tags. Unknown numeric
values remain numeric.

## Orbis target facts

The SDK source configures `x86_64-orbis-freebsd9`, maps the BFD target to
`elf64-x86-64-freebsd`, uses `EM_X86_64` (`0x3e`) with `ELFOSABI_FREEBSD` (`9`), and sets both
minimum and common page sizes to `0x4000`. It also defines
`R_X86_64_ORBIS_GOTPCREL_LOAD` as relocation code `40`: a four-byte, signed 32-bit PC-relative
GOT-load relocation whose final instruction/linker behavior is Sony-specific. The parser preserves
these facts. `artifacts validate-implementation` applies only pure, source-bound formulas after
an explicit original-address or aligned load-base selection; it does not mutate the ELF or infer
a base from IDA/Ghidra defaults.

The standard x86-64 relocation names and widths are reproduced from the SDK's `x86-64.h` and
formula behavior is kept in the versioned evaluator. GOT/PLT, TLS, indirect-relative, and code
`0x28` cases retain their formula and an unresolved status when the required loader/linker state
is absent. Target bytes are read through `PT_LOAD`, while `PT_SCE_DYNLIBDATA` is used only for
SCE metadata tables.

## Key Differences from Standard ELF

1. **No Section Headers**: Many PS4 ELFs omit section headers entirely, relying only on program headers
2. **Custom Dynamic Sections**: Extensive use of SCE-specific dynamic tags for module management
3. **Relocations**: Uses custom relocation types in the SCE range
4. **Encrypted/Signed**: Production PS4 binaries are encrypted and signed (SELF format)
5. **PRX Format**: Dynamic libraries use .prx extension instead of .so
6. **Memory Layout**: Kernel modules use special base address (0xFFFFFFFF82200000)

## Important Notes for Parsing

1. **Lenient Section Parsing**: Must handle missing or NULL section headers
2. **Dynamic Segment Priority**: Information is primarily in program headers and dynamic segment
3. **String Table Duplicates**: May have both standard DT_STRTAB and DT_SCE_STRTAB
4. **Symbol Table Duplicates**: May have both standard DT_SYMTAB and DT_SCE_SYMTAB
5. **Relocation Handling**: Must support SCE-specific relocation formats
