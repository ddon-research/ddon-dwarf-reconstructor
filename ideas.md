# Preformance-related
Here is a list of performance optimization techniques to analyze and plan for in the context of the code base. Please create an implementation plan and write down to the root of the project with enough context so you can pick it up again at any time.
- Review the codebase to ensure we make use of various performance optimization strategies where useful, e.g. hashing, indices, maps, caches, lookup tables, persistence on disk, file compression (zstd), lazy loading, keeping a record of compilation unit offsets etc.
- Initially a specific type's root node (i.e. the node that actually defines the class structure, not the first symbolic reference) has to be found. It should be the first DW_TAG_class_type with DW_AT_name tag that matches. Such classes also usually have a DW_TAG_subprogram with newInstance. Afterwards a per-offset based compilation unit traversal must happen. Then that would mean that additional information about "root" tag -> compilation unit indexes should help speed up performance.
- To enable binary search, the symbol name to CU offset index should be sorted.
- Loading the CU cache from disk can be lazy-loaded and parallelized. For example, if a DW_AT_type is just an offset, e.g 0x000061da, then that is a dependency that can be added to a set of dependencies to load and look up.
- Ther are more than 2k CUs, there should be some binary tree lookup for the symbol the user is looking for. The flow in general should be this:
Identify the root class definition DWARF tag, i.e. the first time the symbol is defined as a class. Afterwards, for all references, identify the compilation unit / offset and look up the remaining information.
- There should be a lightweight unique DW_AT_name lookup table to have early exists on non existant names.
- Add zstd compression to the dwarf cache, on a per DWARF CU basis. Add the necessary python package via uv/pip/pytoml and update the requirements.txt file. The initial generation took >12h, so don't change the interface and to avoid re-generating everything from scratch, make it work with the non-compressed .pkl files as fallback if it can not find a compressed variant. Ensure to write a compressed variant to disk afterwards.
- Parallelize the CU pickling process.
## Maybe?
- Replace pyelftools with a similar setup to dwarf2cpp via pybind and LLVM

# Output-related
- A special simplified, C-like struct-only output
- A special output to optimize Ghidra structures: identify alignment and packing hints per structure (CSV-like: struct class, packing)

# Discrepancies
- Create a detailed plan before starting with enough context so you can pick up the tasks again later, create a TODO list.
- TODO: Improve the knowledge base about pyelftools by analyzing the referenced Git repository in more detail (check references.md), including examples and an overview of classes and methods, this also pays into reducing redundancy and add the new understanding in the CLAUDE.md
- TODO: Update copilot instructions file with the most important recent changes
- README, CLAUDE, copilot instructions and knowledge base are out of date and need updating - TODO: Update documents, stay technical, brief, no sales-like, flowery language
- The native_generator.py is inconsistent in its code pathways and has some code duplication: there is major behavioral difference between full hierarchy and basic mode - TODO: stay DRY
- During the refactoring of native_generator.py the debug information and timing information has been lost. TODO: Improve logging and progress tracking.
- The full hierarchy update for MtPropertyList did not resolve basic primitve types like u16, u32 - TODO: fix this buggy behavior
- Test the output by running the application on something simple and fast like MtObject but also consider the other use cases that have nested structs, unions etc. - TODO: Add new tests to verify parsing of these new tags like enums, structs, unions, operators, typedefs, base types etc.