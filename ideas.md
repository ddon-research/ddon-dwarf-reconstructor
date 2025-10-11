# Header-related
- The headers currently do not resolve all referenced classes. There are too many forwarded declarations instead of resolving the classes.

# Output-related
- A special simplified, C-like struct-only output mode
- A special output to optimize Ghidra structures: identify alignment and packing hints per structure (CSV-like: struct class, packing)
