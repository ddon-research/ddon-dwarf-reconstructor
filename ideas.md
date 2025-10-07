# Preformance-related
- Review the codebase to remove redundant generation hints, there should just be one optimal strategy that makes use of all kinds of techniques: hashing, indices, maps, caches, lookup tables, persistence on disk, file compression, lazy loading, compilation unit offsets etc. Look into references and what they are doing. Initially a specific type's root note has to be found -> it should be the first class tag with name tag that matches. Afterwards a per-offset based compilation unit traversal must happen. Then that would mean that additional information about "root" tag -> compilation unit indexes should help speed up performance.
- Loading the CU cache from disk can be parallelized
- Ther are more than 2k CUs, but the main program currently only loads the first 500 CUs, which makes no sense. Instead, there should be some binary tree lookup for the first root tag. The flow in general should be this:
Identify the root class definition DWARF tag, i.e. the first time the symbol is defined as a class. Afterwards, for all references, identify the compilation unit / offset and look up the remaining information.
Currently we are just caching all the CUs. But there needs to be a binary search tree compatible approach to storing a lookup of: class definition -> offset to look up the CUs fast.
- FIXME: The program should have an early stop for initial CU-finding. (DONE) => Follow-up: There should be a parallel search whenever a CU is loaded to check if it contains the root tag for the target symbol.
- There should be a lightweight unique DW_AT_name lookup table to have early exists on non existant names.
- Add zstd compression to the dwarf_cache, per CU.
- Parallelize the CU pickling process.

# Output-related
- Add all sorts of meta information like sizes, offsets, alignment via inline comments
- A complete reconstruction of the C++ class with access modifiers, vtables, function signatures etc.
- A special simplified, C-like struct-only output
- A special output to optimize Ghidra structures: identify alignment and packing hints per structure (CSV-like: struct class, packing), for example the packing for some structs is 1-bit aligned, i.e. maximally packed. This is the case for some of the cSetInfoOm hierarchy, but not all of them! Some are actually 8-bit aligned.

# Maybe?
- Replace pyelftools with a similar setup to dwarf2cpp via pybind and LLVM

# Setup-related
- FIXME: Weirdly two main.py, the one in root doesn't do anything...

# Test-related
Please review test setup in detail and create a plan for refactoring.
Current issues: 
- recently a pytest-based setup has been introduced, but there still remains a run_tests.py file which manually handles discovery of tests. This should no longer be used.
- Additionally there is a README in the tests folder that needs to be updated.
- Additionally, the logical tests that make use of some sample resource to look for should make use of known samples like "MtObject", check the sample-symbols.csv
- Update the CLAUDE.md such that it is mandatory to run all tests via pytest