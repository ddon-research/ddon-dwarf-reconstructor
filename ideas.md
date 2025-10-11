# Header-related
- The headers currently do not resolve all referenced classes. There are too many forwarded declarations instead of resolving the classes.

# Output-related
- A special simplified, C-like struct-only output mode
- A special output to optimize Ghidra structures: identify alignment and packing hints per structure (CSV-like: struct class, packing)

# Discrepancies
- Create a detailed design and implementation plan before starting with enough context so you can pick up the tasks again later and keep track of a TODO list ultrathink
- README, CLAUDE, copilot instructions and knowledge base are out of date and need updating - TODO: Update documents, stay technical, brief, no sales-like, flowery language ultrathink
- Test the output by running the application and the unit tests ultrathink
