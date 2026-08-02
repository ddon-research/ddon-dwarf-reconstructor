# DDON DWARF Reconstructor - Knowledge Base

This knowledge base documents our approach to DWARF-to-C++ header reconstruction. 

**Core Principle**: We use pyelftools directly without reinventing DWARF parsing APIs or data structures.

## Directory Structure

```
knowledge-base/
├── dwarf-specification/  # Canonical DWARF 2/3/4 JSON and Markdown
│   ├── generated/        # Checked-in artifacts and deterministic manifest
│   └── README.md         # Build and provenance contract
├── ps4-elf/             # PS4-specific ELF format information
│   ├── ps4-constants.md
│   └── ida-loader-insights.md
├── dwarf/               # DWARF parsing techniques
│   ├── ghidra-dwarf-parsing.md
│   └── llvm-dwarf-parsing.md
├── pyelftools/          # Current implementation approach
│   └── pyelftools-approach.md
├── tools/               # Related tools and their approaches
│   └── dwarf2cpp-approach.md
├── optimization/        # Performance optimization strategies
│   └── indexing-strategy.md
└── observability/        # Structured logs, tracebacks, and telemetry seam
    ├── README.md
    └── structured-logging-and-exception-tracing.md
```

## Machine-readable DWARF specifications

The standalone [`tools/dwarf_spec_pipeline/`](../../tools/dwarf_spec_pipeline/)
project downloads checksum-locked official `.mm`/`.doc` sources and publishes
the canonical artifacts in `dwarf-specification/generated/`. Docker Compose is
the reproducible conversion environment on Windows and Ubuntu; `uv` manages
the ordinary Python development and test environment. Use the
[dwarf-specification README](dwarf-specification/README.md) for the full
contract, commands, source provenance, and schema link.

## Sources

### PS4 ELF Parsing

1. **GhidraOrbis** (Java)
   - Source: https://github.com/astrelsky/GhidraOrbis
   - Local: `D:\GhidraOrbis\src\main\java\orbis`
   - Focus: Production-quality PS4 ELF loader for Ghidra
   - Key insights: PS4 constants, dynamic section handling, section-less ELFs

2. **ps4_module_loader** (Python/IDA)
   - Source: https://github.com/SocraticBliss/ps4_module_loader
   - Local: `E:\HackingEmulation\IDA\ps4_module_loader`
   - Focus: IDA Pro loader for PS4 modules
   - Key insights: Base address handling, segment classification, architecture validation

### DWARF Parsing

3. **Ghidra DWARF Parser** (Java)
   - Source: https://github.com/NationalSecurityAgency/ghidra
   - Local: `D:\ghidra\Ghidra\Features\Base\src\main\java\ghidra\app\util\bin\format\dwarf`
   - Focus: Industrial-strength DWARF parser
   - Key insights: Lazy loading, index-based trees, abbreviation caching, optimization strategies

4. **pyelftools** (Python) - **OUR FOUNDATION**
   - Source: https://github.com/eliben/pyelftools
   - Status: **Primary dependency - we use their API directly**
   - Focus: Pure Python ELF/DWARF parsing with proven stability
   - **Our commitment**: Use pyelftools classes (`DWARFInfo`, `DIE`, etc.) without reinvention

5. **LLVM DWARF Parser** (C++)
   - Source: https://github.com/llvm/llvm-project
   - Local: `D:\llvm-project\llvm\lib\DebugInfo\DWARF`
   - Focus: Production DWARF parser used by Clang, lldb, and many tools
   - Key insights: Thread safety, accelerator tables, type reconstruction, error recovery

### Tools and Applications

6. **dwarf2cpp** (Python + C++ via pybind11)
   - Source: https://github.com/endstone-insider/dwarf2cpp
   - Local: `D:\dwarf2cpp\src\dwarf2cpp`
   - Focus: Generate C++ headers from DWARF debug information
   - Key insights: LLVM integration via pybind11, visitor pattern, type reconstruction, caching

### Reference Implementation

7. **libdwarf** (C)
   - Source: https://github.com/davea42/libdwarf-code
   - Local: `C:\msys64\home\morph\libdwarf-code\src\lib\libdwarf`
   - Focus: Official DWARF reference implementation
   - Status: Not yet fully analyzed

## Key Findings Summary

### PS4 ELF Specifics

- **No Section Headers**: Many PS4 ELFs omit section headers entirely
- **Custom Segment Types**: 0x6100xxxx range for Sony-specific segments
- **Custom ELF Types**: 0xFExx range for PS4 executables/libraries
- **Dynamic Tags**: Extensive SCE-specific dynamic section tags
- **Memory Layout**: Special handling for kernel modules, ASLR

### DWARF Parsing Strategies

| Approach | Memory | Speed | Complexity | Best For |
|----------|--------|-------|------------|----------|
| **Eager (pyelftools)** | High | Moderate | Low | Small-medium files |
| **Lazy (Ghidra/LLVM)** | Low | Fast | High | Large files, production |
| **Hybrid (Our approach)** | Medium | Fast | Medium | Multiple searches |
| **LLVM via pybind11** | Low | Very Fast | Medium | Production tools |

### Critical Implementation Details

1. **PS4 Compatibility**
   - Must patch pyelftools for non-standard sections
   - Handle NULL section types gracefully
   - Prioritize program headers over sections

2. **Performance Optimization**
   - Cache abbreviations per compilation unit
   - Consider lazy attribute loading for large files
   - Use index-based relationships for memory efficiency
   - Early-exit searches when target found

3. **Error Handling**
   - Skip empty compilation units silently
   - Continue on non-fatal parsing errors
   - Validate DWARF version support early
   - Provide informative error messages

## Recommendations for Our Implementation

### Current Status ✅
- ✅ **Enhanced PS4 ELF support** with comprehensive patches (dynamic sections, SCE tags, automatic detection)
- ✅ Type-safe models with dataclasses
- ✅ Search utilities (by name, tag, predicate)
- ✅ Configuration management (.env support)
- ✅ Fast search by using pyelftools' iter_DIEs() directly


### Future Enhancements 🔄

1. **Performance** (if needed)
   - Implement lazy attribute loading (not yet implemented)
   - Add persistent index cache to disk (not yet implemented)
   - Memory-mapped indexes for very large files
   - Consider LLVM integration via pybind11 for 10-100x speedup

2. **Features**
   - Support more PS4-specific ELF features
   - Add type reconstruction from DWARF (use LLVM's DWARFTypePrinter)
   - Generate C/C++ header files (similar to dwarf2cpp)
   - Visitor pattern for cleaner DIE traversal
   - Accelerator table support for O(1) lookups

3. **Robustness**
   - More comprehensive error recovery (LLVM-style handlers)
   - Better handling of malformed DWARF
   - Support for DWARF v5 features
   - Thread-safe parsing for parallel processing

## Using This Knowledge Base

### For Development
- Consult `ps4-elf/ps4-constants.md` when adding PS4 ELF handling
- Reference `dwarf/ghidra-dwarf-parsing.md` for optimization ideas
- Check `dwarf/llvm-dwarf-parsing.md` for production-quality patterns
- Review `tools/dwarf2cpp-approach.md` for header generation and LLVM integration
- Check `pyelftools/pyelftools-approach.md` for API patterns
- Review `optimization/indexing-strategy.md` for performance tuning
- Review `observability/` for event fields, exception traces, and future telemetry integration

### For Debugging
- Compare behavior with Ghidra/IDA implementations
- Validate constants against multiple sources
- Test edge cases documented in insights files

### For Documentation
- Link to specific sections in knowledge base docs
- Update knowledge base when discovering new patterns
- Add examples and test cases based on insights

## Contributing

When adding to this knowledge base:
1. Extract actionable insights, not just code dumps
2. Compare approaches across implementations
3. Document trade-offs and recommendations
4. Update this README with new sources
5. Add examples where helpful
