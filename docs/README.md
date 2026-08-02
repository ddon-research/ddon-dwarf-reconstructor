# Documentation Index

Complete documentation for the DWARF-to-C++ header reconstructor.

## Quick Links

### Getting Started
- [README](../README.md) - Project overview, installation, and usage examples
- [TESTING](TESTING.md) - Testing strategy, running tests, and coverage
- [SONARQUBE](SONARQUBE.md) - Local SonarQube for VS Code C/C++ analysis with MSVC
- [LANGFUSE_TRACING](LANGFUSE_TRACING.md) - Local Langfuse tracing for Copilot and Codex

### Architecture Documentation
- [ARCHITECTURE](ARCHITECTURE.md) - Complete architecture documentation with design rationale
- [COMPONENT_DIAGRAM](COMPONENT_DIAGRAM.md) - Visual class diagram showing all components and relationships
- [GENERATION_FLOWS](GENERATION_FLOWS.md) - Step-by-step flowcharts for single-file and multi-file generation modes

### Technical Reference
- [DWARF_TAG_ANALYSIS](DWARF_TAG_ANALYSIS.md) - DWARF tag analysis and classification
- [PS3_DWARF2_LOCATION_EXPRESSIONS](PS3_DWARF2_LOCATION_EXPRESSIONS.md) - PS3 DWARF2 location expression handling
- [LANGFUSE_TRACING](LANGFUSE_TRACING.md) - Docker Compose operations and agent configuration

### Knowledge Base
- [knowledge-base/](knowledge-base/) - Research notes, external references, and technical investigations
  - [dwarf-specification/](knowledge-base/dwarf-specification/) - Official DWARF 2 and DWARF 4 specifications
  - [dwarf/](knowledge-base/dwarf/) - DWARF parsing patterns from other projects
  - [pyelftools/](knowledge-base/pyelftools/) - pyelftools API reference and examples
  - [ps4-elf/](knowledge-base/ps4-elf/) - PS4 ELF format specifics
  - [tools/](knowledge-base/tools/) - Analysis of similar tools

## Document Overview

### ARCHITECTURE.md
**Purpose:** Comprehensive architecture documentation focusing on current capabilities and design rationale.

**Contents:**
- Purpose and scope (Dragon's Dogma Online reverse engineering)
- System architecture (domain-driven design layers)
- Directory structure with component explanations
- Core components detailed documentation
- Design principles and rationale (offset-based resolution, lazy loading, etc.)
- Performance characteristics with complexity analysis
- Limitations and trade-offs
- Testing strategy
- Platform-specific validation (PS3 vs PS4)
- Extension points for custom implementations

**When to read:** Understanding the overall system design, why certain approaches were chosen, and how components interact.

### COMPONENT_DIAGRAM.md
**Purpose:** Visual representation of all classes and their relationships.

**Contents:**
- Complete mermaid class diagram with all components
- Component responsibilities by layer (Application, Domain, Core, Infrastructure)
- Relationships and dependencies between components
- Quick reference for understanding the codebase structure

**When to read:** Getting oriented in the codebase, understanding component boundaries, seeing the big picture.

### GENERATION_FLOWS.md
**Purpose:** Step-by-step visual workflows for header generation modes.

**Contents:**
- Single-file generation flowchart with color-coded steps
- Multi-file generation flowchart with FileRegistry integration
- Shared helper methods diagram showing code reuse
- Data flow comparison table
- Performance characteristics by mode
- Use case recommendations

**When to read:** Understanding how header generation works end-to-end, comparing single-file vs multi-file modes, debugging generation issues.

### TESTING.md
**Purpose:** Testing strategy, guidelines, and how to run tests.

**Contents:**
- Quick start commands
- Test categories (unit vs integration)
- Test structure and organization
- Writing new tests with examples
- Coverage requirements and CI/CD integration
- Performance benchmarks
- Troubleshooting common issues

**When to read:** Running tests, writing new tests, understanding test coverage requirements.

### SONARQUBE.md

**Purpose:** Local SonarQube for VS Code C/C++ analysis using the Visual Studio MSVC toolchain.

**Contents:**

- Sonar Build Wrapper installation outside the repository
- MSVC compilation-database generation
- VS Code activation and troubleshooting

**When to read:** Setting up or refreshing SonarQube analysis for generated C++ headers.

### DWARF_TAG_ANALYSIS.md
**Purpose:** Analysis of DWARF tags and type classification.

**Contents:**
- DWARF tag taxonomy
- Type classification rules
- Tag usage patterns in PS4 ELF files
- Handling special cases (forward declarations, anonymous types)

**When to read:** Understanding DWARF tag handling, debugging parsing issues, adding support for new tags.

### PS3_DWARF2_LOCATION_EXPRESSIONS.md
**Purpose:** PS3-specific DWARF2 location expression parsing.

**Contents:**
- DWARF2 vs DWARF3/4 differences
- Location expression format for PS3
- Offset extraction algorithms
- Platform detection logic

**When to read:** Working on PS3 support, debugging location expression parsing.

## Navigation Guide

### I want to understand...

**...how the system works overall**
1. Start with [README](../README.md) for high-level overview
2. Read [ARCHITECTURE](ARCHITECTURE.md) for detailed design
3. View [COMPONENT_DIAGRAM](COMPONENT_DIAGRAM.md) for visual structure

**...how to generate headers**
1. Check [README](../README.md) usage examples
2. Follow [GENERATION_FLOWS](GENERATION_FLOWS.md) for step-by-step workflows
3. Refer to [ARCHITECTURE](ARCHITECTURE.md) for component details

**...how to run tests**
1. [TESTING](TESTING.md) has all commands and guidelines
2. [README](../README.md) has quick test commands
3. [ARCHITECTURE](ARCHITECTURE.md) explains testing strategy rationale

**...why certain design decisions were made**
1. [ARCHITECTURE](ARCHITECTURE.md) has extensive rationale sections
2. [GENERATION_FLOWS](GENERATION_FLOWS.md) explains shared helper rationale
3. Check git history and commit messages for historical context

**...how to add new features**
1. [ARCHITECTURE](ARCHITECTURE.md) explains extension points
2. [COMPONENT_DIAGRAM](COMPONENT_DIAGRAM.md) shows where to add code
3. [TESTING](TESTING.md) explains how to add tests
4. [ARCHITECTURE](ARCHITECTURE.md) "Future Directions" section has ideas

**...how DWARF parsing works**
1. [DWARF_TAG_ANALYSIS](DWARF_TAG_ANALYSIS.md) for tag classification
2. [PS3_DWARF2_LOCATION_EXPRESSIONS](PS3_DWARF2_LOCATION_EXPRESSIONS.md) for PS3 specifics
3. [knowledge-base/dwarf/](knowledge-base/dwarf/) for external references
4. [ARCHITECTURE](ARCHITECTURE.md) for ClassParser and TypeResolver details

## Documentation Principles

The documentation follows these principles:

1. **Present-tense focus:** Describes what exists and why, not what changed
2. **Technical and concise:** No fluff, marketing language, or emojis
3. **Code examples:** Real code from the project, not pseudocode
4. **Visual aids:** Diagrams, tables, and flowcharts for complex concepts
5. **Cross-references:** Links between related documents
6. **Rationale-driven:** Explains WHY decisions were made for THIS project

## Contributing to Documentation

When updating documentation:

1. **Keep focused:** Each file has a specific purpose
2. **Update cross-references:** Check for links in other files
3. **Add examples:** Prefer real code over descriptions
4. **Explain rationale:** Why this approach for Dragon's Dogma Online reconstruction?
5. **Verify accuracy:** Run the code, check metrics, validate claims
6. **Maintain style:** Follow existing formatting and tone

## Historical Context

Historical information (what changed, when, and why) belongs in:
- Git commit messages and history
- Refactoring plan documents (e.g., `REFACTORING_PLAN_*.md`)
- NOT in architecture documentation

Architecture documentation explains the current state and design rationale.
