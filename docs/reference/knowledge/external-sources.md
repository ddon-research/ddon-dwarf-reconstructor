# External sources

The project uses external sources as research or additive evidence, not as an unqualified source
of PS4 semantics. The most important references are:

- [pyelftools](https://github.com/eliben/pyelftools) for Python ELF/DWARF parsing APIs.
- [Ghidra](https://github.com/NationalSecurityAgency/ghidra) and
  [GhidraOrbis](https://github.com/astrelsky/GhidraOrbis) for generic and PS4-oriented comparison.
- [libdwarf](https://github.com/davea42/libdwarf-code) for DWARF reference behavior.
- [LLVM DWARF](https://github.com/llvm/llvm-project/tree/main/llvm/lib/DebugInfo/DWARF) for a
  second generic parser implementation.
- [dwarf2cpp](https://github.com/endstone-insider/dwarf2cpp) for reconstruction comparison.

The authoritative boundary for an external-tool run is recorded in its manifest. Consult the
[external-tool evidence notes](../../knowledge-base/tools/external-tool-evidence.md) before
promoting a comparison result into a project contract.
