# Feature
- A special simplified, C-like struct-only output mode

# Feature
- A special output to optimize Ghidra structures: identify alignment and packing hints per structure (CSV-like: struct class, packing)

# Feature
- Add namespace information to types, enums, classes etc.

# Enhancement: Cache Metadata for Complete Definition Detection

## Problem
Currently, the persistent symbol cache stores only symbol name → DIE offset mappings. When the cache is loaded, validation must occur at retrieval time to check if the cached offset points to a complete class definition or just a forward declaration. This validation requires loading the DIE and checking the `DW_AT_declaration` attribute, which adds overhead.

## Proposed Solution
Enhance cache entries to store completeness metadata alongside offsets:

```python
{
    "symbol_name": {
        "offset": 0x12345,
        "cu_offset": 0x100,
        "is_complete": true,          # New: not a forward declaration
        "has_children": true,          # New: has members/methods
        "byte_size": 128,              # New: size in bytes
        "completeness_score": 10128    # New: pre-calculated score
    }
}
```

## Benefits
1. **Skip validation overhead**: Cache hit can immediately determine if entry is usable
2. **Faster filtering**: Can reject incomplete definitions without loading DIE
3. **Better cache utilization**: Know quality of cached entries
4. **Pre-computed scoring**: No need to recalculate completeness score

## Trade-offs
1. **Larger cache files**: More metadata per entry (~16-24 extra bytes)
2. **Cache invalidation complexity**: Need to update cache when parsing logic changes
3. **Migration overhead**: Existing caches need conversion or rebuild

## Current Implementation (Validation-on-Retrieval)
The current approach keeps cache entries simple and performs validation when retrieving:
- **Pros**: Simple cache format, no migration needed, always uses latest validation logic
- **Cons**: Validation overhead on every cache hit, potential wasted lookups

## Recommendation
Keep validation-on-retrieval approach for now due to:
1. Cache rebuild is already expensive (full ELF scan), validation overhead is marginal
2. Simpler cache format reduces bugs and maintenance
3. Validation logic may evolve as DWARF edge cases are discovered
4. Current performance is acceptable for MTFramework use case

Consider metadata enhancement if:
- Cache validation becomes a measurable bottleneck (profile first)
- Multiple cache hits per symbol lookup become common
- Cache format stabilizes (no breaking changes for 6+ months)

## Implementation Notes
If implementing metadata enhancement:
1. Add versioning to cache format for migration detection
2. Include timestamp or ELF hash for cache invalidation
3. Store DWARF version used during cache build
4. Provide tool to inspect and validate cache contents
5. Document cache format in ARCHITECTURE.md

# Bug
- rAbilityAddData is not found/understood, it is part of a namespace and generates an empty file

# Bug
- rStageList, rStageAdjoinList, rStaminaDecTbl, rStartPosArea is unexpectedly empty
For example, according to IDA Pro it should roughly look like this:
```
struct __cppobj __attribute__((aligned(8))) rStageAdjoinList : cResource
{
  rStageAdjoinList::AdjoinInfoArray mAdjoinInfo;
  rStageAdjoinList::JumpPositionArray mJumpPosition;
  u16 mStageNo;
};
```

# Bug
- Array types are still generated with the wrong declaration syntax
```
class STRING
{
public:
    s32 ref;  // offset: 0x0
    u32 length;  // offset: 0x4
    u8[] str;  // offset: 0x8
};
```

# Bug
- When a function has multiple "formal parameters", avoid generating the name "param", as that just leads to syntax errors and method signatures in declarations do not need any parameter names and we don't have access to them anyway => Question is how does IDA recover parameter names? e.g. "bool __fastcall cResource::convertEx(cResource *this, MtStream *, cResource::CONVERT_TYPE type);"
- Reconstructing / providing vtable information via "DW_AT_vtable_elem_location" e.g. in 
```
0x0001326c:     DW_TAG_subprogram [55] * (0x00012e3f)
                  DW_AT_name [DW_FORM_strp]     ( .debug_str[0x00006899] = "convertEx")
                  DW_AT_decl_file [DW_FORM_data1]       ("D:\publishDDO_PS4_02_02_Master\DDO_02_02\DD_ONLINE/..\capdev200\XFramework/cResource.h")
                  DW_AT_decl_line [DW_FORM_data1]       (239)
                  DW_AT_type [DW_FORM_ref4]     (cu + 0x12f2 => {0x00001f8f} "bool")
                  DW_AT_virtuality [DW_FORM_data1]      (DW_VIRTUALITY_virtual)
                  DW_AT_vtable_elem_location [DW_FORM_exprloc]  (DW_OP_constu 0xe)
                  DW_AT_declaration [DW_FORM_flag_present]      (true)
                  DW_AT_external [DW_FORM_flag_present] (true)
                  DW_AT_accessibility [DW_FORM_data1]   (DW_ACCESS_protected)
                  DW_AT_containing_type [DW_FORM_ref4]  (cu + 0x121a2 => {0x00012e3f} "cResource")

0x00013280:       DW_TAG_formal_parameter [6]   (0x0001326c)
                    DW_AT_type [DW_FORM_ref4]   (cu + 0x1273b => {0x000133d8} "cResource *")
                    DW_AT_artificial [DW_FORM_flag_present]     (true)

0x00013285:       DW_TAG_formal_parameter [15]   (0x0001326c)
                    DW_AT_type [DW_FORM_ref4]   (cu + 0x12740 => {0x000133dd} "MtStream &")

0x0001328a:       DW_TAG_formal_parameter [15]   (0x0001326c)
                    DW_AT_type [DW_FORM_ref4]   (cu + 0x125f3 => {0x00013290} "cResource::CONVERT_TYPE")

0x0001328f:       NULL

```


DONE: Upgrade Python to 3.14.6, I already installed it via uv. Enforce it at all levels.
--
DONE: 
Review the tooling setup and check for best practices outlined here:
[cookiecutter/cookiecutter](https://github.com/cookiecutter/cookiecutter)
[audreyfeldroy/cookiecutter-pypackage](https://github.com/audreyfeldroy/cookiecutter-pypackage)
[casey/just](https://github.com/casey/just)
[facebook/pyrefly](https://github.com/facebook/pyrefly)
[fastapi/typer](https://github.com/fastapi/typer)
[osprey-oss/deptry](https://github.com/osprey-oss/deptry)

Specifically, I want you to review our existing CLI setup and check how to migrate to typer. We are mainly a CLI-based application. Improving the interface and reducing boilerplate is important, similar to what you can do with Picocli in Java.
I also want you to check our mypy-based setup and check how to migrate to pyrefly. VSCode seems to also report that we are running Pyrefly already but in Legacy mode and that we need to run init. We should improve that.
Check how "just" can improve the existing setup and improve automation or if it competes with anything existing.
Check other best practices in the cookiecutter setup since this standardizes the project setup.
Include dependency quality checks via deptry.
Afterwards, review the current copilot and codex instructions and revalidate the tooling loop for changes. Update the python instructions as well.
--
DONE: 
Review whether the scripts folder is really needed. I think we should stick to standard CLI tooling or wrap it with just/Python code. This scripts-folder pattern goes against our new approach, at the very least the random ps1 powershell scripts do.
Also make sure the reconstructor can be installed as a uv tool.
--
DONE: 
Review improvements to the existing hexagonal architecture by deriving patterns and best practices from these sources:
Reference:
https://en.wikipedia.org/wiki/Hexagonal_architecture_(software)
https://alistair.cockburn.us/hexagonal-architecture
https://wiki.c2.com/?HexagonalArchitecture
https://wiki.c2.com/?PortsAndAdaptersArchitecture
https://github.com/dohorn/java/blob/f18fdad9f97a0608b6a7d5b19a5c392859bacaea/modules/ROOT/pages/architecture/hexagonal_architecture.adoc
Afterwards refactor and replace the custom architectural unit tests using something that reduces boilerplate, decide between:
https://github.com/zyskarch/pytestarch
https://github.com/LukasNiessen/ArchUnitPython
or some other alternative.
Ensure hexagonal architecture is enforced.
--
DONE:
Reference: [https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex](https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex)
Optimize the following activity for a /goal oriented workflow for the ddon-dwarf-reconstructor:

Review the whole codebase and identify subtle bugs and false or brittle assumptions.
Review the code base and identify a refactoring plan from this perspective: remove any hints towards backwards compatibility and legacy-related language. Clean architecture is more important, we don't care about breaking changes. Remove abstractions that only exist to avoid refactoring. Replace any helpers that only exist because we haven't introduced the right patterns yet.

Afterwards, review the current copilot, codex, python instructions and revalidate the tooling loop for changes. Update documentation, specs and the knowledge base.
Derive a plan first and refactor the code aggressively.
--
DONE:
We went through large refactoring. Clean all artifact caches and temporary and intermediate files. Also clean dot (".") folders, if any, unless it would break our setup/IDE. Then regenerate them all to ensure we have not introduced any regressions by accident. It might make sense to compare the previous results and fil.es and keep them in an archive before deleting them and until we are sure nothing is broken.
--
DONE:
Reference: [https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex](https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex)
Optimize the following activity for a /goal oriented workflow for the ddon-dwarf-reconstructor:

Review the testing setup. Follow the testing pyramid. Do we have enough functional and non-functional tests? We should not just rely on unit tests and technical tests.
We need to have appropriate well-understood regression and integration tests. We should make sure we categorize our tests based on the purpose they fulfill, e.g. performance tests should be marked as such. We should make sure critical integration tests are not opt-in but are actually part of the testing loop, regardless of slowness.
References:
https://www.tdda.info/tagging-pytest-tests
https://realpython.com/pytest-python-testing/
https://www.geeksforgeeks.org/python/grouping-the-tests-in-pytest/
https://medium.com/homeaway-tech-blog/write-better-python-with-hypothesis-5b31ac268b69
https://hypothesis.readthedocs.io/en/latest/quickstart.html
https://realpython.com/ref/best-practices/code-testing/
https://docs.python-guide.org/writing/tests/
https://martinfowler.com/articles/practical-test-pyramid.html
https://www.geeksforgeeks.org/python/python-pyramid-testing/
https://realpython.com/ref/software-engineering-glossary/test-pyramid/

Afterwards, review the current copilot, codex, python instructions and revalidate the tooling loop for changes. Update documentation, specs and the knowledge base.
Derive a plan first and refactor the code aggressively.
--
DONE:
Reference: [https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex](https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex)
Optimize the following activity for a /goal oriented workflow for the ddon-dwarf-reconstructor:

Identify ways to improve observability, traceability, debuggability, instrumanetability by choosing the right logging setup, framework and approach. I am partial towards anything that can support things like open telemetry in the future and are extensible and will support JSON and end-to-end tracing and support rich exception stack traces with line references and nestedness like in Java.
As the application gets more complex we need better logs that help us find bugs faster in a pin-pointed way. Structlog seems to support this.
Check the references:
https://www.highlight.io/blog/5-best-python-logging-libraries
https://www.dash0.com/guides/python-logging-libraries
https://docs.python.org/3/library/logging.html
https://docs.python.org/3/library/traceback.html
https://github.com/hynek/structlog
https://www.structlog.org/en/stable/
https://www.structlog.org/en/stable/getting-started.html
https://realpython.com/ref/best-practices/logging/
https://betterstack.com/community/guides/logging/python/python-logging-best-practices/
https://www.bugsink.com/blog/capture-stacktrace-no-exception/
https://docs.python.org/3/howto/logging.html
https://stackoverflow.com/questions/63404899/combining-python-trace-information-and-logging
Review the whole codebase and check for spots where we should add warning, debug and error logs. Some simple info logs to understand pipeline/stage progress is also needed.
Associated with that is good exception handling. Identify gaps and consider refactoring our setup so far.
References:
https://docs.python.org/3/tutorial/errors.html
https://docs.python.org/3/library/exceptions.html
https://www.geeksforgeeks.org/python/python-exception-handling/
https://realpython.com/python-exceptions/
https://blog.miguelgrinberg.com/post/the-ultimate-guide-to-error-handling-in-python
https://realpython.com/ref/best-practices/exception-handling/
https://jerrynsh.com/python-exception-handling-patterns-and-best-practices/
https://mimo.org/glossary/python/error-handling


Highest priority is on improving existing critical code paths with appropriate logging statements and exception handling.
Structured logs that also expose input/output and data objects for tracing or optional performance would be ideal.
But be careful not to be too verbose and spam logs, otherwise they will be hard to digest and understand.

Afterwards, review the current copilot, codex, python instructions and revalidate the tooling loop for changes. Update documentation, specs and the knowledge base.
Derive a plan first and refactor the code aggressively.
--
DONE:
Reference: [https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex](https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex)
Optimize the following activity for a /goal oriented workflow for the ddon-dwarf-reconstructor:

The PS4 ELF binary likely uses some subset/form of DWARF2-DWARF4 variation, since the game was developed for PS4 which is based on freebsd and it ran on earlier versions of the PS4 up until roughly 2018. This should be verifiable by inspecting the headers and/or checking on the existing LLVM-based DWARF dump/export.
Check our current conceptual assumptions and usage of DWARF symbols against the newly exported DWARF2, DWARF3, and DWARF4 specifications. These are large technical specifications, it might be necessary to first build an index or further extract information out of these.
Validate gaps and wrong relationships or understanding. Accuracy and correctness is paramount. While the DWARF data may be game-specific, the underlying DWARF structure is well-defined and ultimately related to the original C++ code base which is why the loop back check with MSVC is important on the final generated files. We are essentially writing a converter in this pipeline: original C++ (unavailable) -> embedded DWARF debug data -> binary PS4 ELF file -> parse assembly + DWARF AST -> generate C++ header stubs -> reverse engineer methods -> recompile code (final goal)
Thus, getting the DWARF parsing correct is important.

Afterwards, review the current copilot, codex, python instructions and revalidate the tooling loop for changes. Update documentation, specs and the knowledge base.
Derive a plan first and refactor the code aggressively.
--
DONE:
Reference: [https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex](https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex)
Optimize the following activity for a /goal oriented workflow for the ddon-dwarf-reconstructor:

More aggressively incorporate tools from existing LLVM and Orbis toolchains and other common binary inspection/de-/compilation tools that would generate useful one-time exports/dumps which we could integrate into our knowledge base/indexes. We just have to be careful about PS4 ABI support. Since these are mostly well-established command line tools, they should all have valuable --help outputs as a starting point. Investigate them and incorporate their knowledge/concepts.
Building a custom Docker container with compose that includes useful debugging and probing toolchains for binary files could also be helpful.
The goal is to find/derive new potential information sources and refactor the code and adapt our ingestion/lookups with potential new metadata.

References:
Sony official PS4 Orbis tools here 8.0: D:\SCE\ORBIS SDKs\8.000\host_tools
Sony official PS4 Orbis toolchain source code 4.5: E:\HackingEmulation\PlayStation4\ps4-4.5-sdk\Toolchain-4.500
Sony official PS4 Orbis SDK source code 4.5: E:\HackingEmulation\PlayStation4\ps4-4.5-sdk\SDK-4.508.001
GNU Binutils - https://www.gnu.org/software/binutils/binutils.html, available in msys2
LLVM Toolchain - https://llvm.org/docs/CommandGuide/index.html, installed in msys2: C:\msys64\ucrt64\bin
Elfutils - https://github.com/roolebo/elfutils
Libdwarf - https://github.com/davea42/libdwarf-code, available in msys2 / here: C:\msys64\home\morph\libdwarf-code-code-2025-10-06-build-withelf
Pyelftools - https://github.com/eliben/pyelftools
LIEF - https://github.com/lief-project/LIEF
OpenOrbis - https://github.com/OpenOrbis/OpenOrbis-PS4-Toolchain, https://github.com/OpenOrbis/readoelf
https://github.com/ps4-payload-dev/elfldr
https://www.psdevwiki.com/ps4/SELF_-_SPRX


Afterwards, review the current copilot, codex, python instructions and revalidate the tooling loop for changes. Update documentation, specs and the knowledge base.
Derive a plan first and refactor the code aggressively.
--
DONE:
Reference: [https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex](https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex)
Optimize the following activity for a /goal oriented workflow for the ddon-dwarf-reconstructor:

Check the GitHub Actions failures and dependabot PRs and validate the proposed changes:
https://github.com/ddon-research/ddon-dwarf-reconstructor/pulls
https://github.com/ddon-research/ddon-dwarf-reconstructor/actions
Most of the PRs are failing due to the correctness tests: https://github.com/ddon-research/ddon-dwarf-reconstructor/actions/runs/30774416064/job/91567057120?pr=7 & https://github.com/ddon-research/ddon-dwarf-reconstructor/actions/runs/30774416064/workflow?pr=7

Afterwards, review the current copilot, codex, python instructions and revalidate the tooling loop for changes. Update documentation, specs and the knowledge base.
Derive a plan first and refactor the code aggressively.
--
DONE:
Reference: [https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex](https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex)
Optimize the following activity for a /goal oriented workflow for the ddon-dwarf-reconstructor:

Review the CI setup and the GitHub Actions workflows. Check if they are validating the right things compared to our local setup. Ensure all actions in use are up to date. Check if there are low effort integrations provided by GitHub and best practices we should follow. Make sure we stick to the free plan features. Also check in awesome-copilot for useful skills/agents that could help us out here. Improve instructions: 
https://github.com/github/awesome-copilot/blob/main/agents/github-actions-expert.agent.md
https://github.com/github/awesome-copilot

Useful tools:
https://github.com/github/github-mcp-server
https://cli.github.com/manual/

References:
https://docs.github.com/en/actions/tutorials/build-and-test-code/python
https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
https://docs.github.com/en/actions/concepts/workflows-and-actions/workflows
https://docs.github.com/en/code-security/concepts/supply-chain-security/supply-chain-security
https://docs.github.com/en/code-security/concepts/code-scanning/code-scanning
https://docs.github.com/en/code-security/concepts/secret-security/secret-leakage-risks
https://docs.github.com/en/code-security/concepts/secret-security/secret-scanning
https://docs.github.com/en/code-security/concepts/code-scanning/tool-status-page
https://docs.github.com/en/code-security/concepts/code-scanning/codeql/codeql-code-scanning
https://docs.github.com/en/code-security/concepts/supply-chain-security/best-practices-for-maintaining-dependencies
https://docs.github.com/en/code-security/concepts/supply-chain-security/dependency-graph-data
https://docs.github.com/en/code-security/concepts/supply-chain-security/about-the-dependabot-yml-file
https://docs.github.com/en/code-security/concepts/supply-chain-security/dependency-graph
https://github.com/github/awesome-copilot/blob/main/instructions/markdown.instructions.md
https://learn.chatgpt.com/docs/agent-configuration/agents-md

Afterwards, review the current copilot, codex, derive new GHA instructions (check https://github.com/github/awesome-copilot/blob/main/instructions/github-actions-ci-cd-best-practices.instructions.md, https://github.com/github/awesome-copilot/blob/main/instructions/markdown-content-creation.instructions.md as foundation & https://github.com/github/awesome-copilot/blob/main/instructions/instructions.instructions.md) and revalidate the tooling loop for changes. Update documentation, specs and the knowledge base.
Derive a plan first and refactor the code aggressively.
--
DONE:
Reference: [https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex](https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex)
Optimize the following activity for a /goal oriented workflow for the ddon-dwarf-reconstructor:



Scan the entire codebase and documentation. Completely revamp the documentation approach. Introduce a wiki-like setup with a knowledge graph. I want to have a static site publishable to GitHub pages. Consider we need functional and technical documentation incl. high-level architecture and low-level solution approaches. Check out the following resources and derive the next best step. I am leaning toward zensical as tool with arc42-style docs for architecture and an overarching diataxis-style approach. Diagrams and visualizations should be generated with an as-code approach using mermaid. Make use of UML diagrams. Our specs should serve as a roadmap. Identify gaps, fill them based on the source code analysis and how things currently work and throw away all obsolete documentation. 
https://github.com/zensical/zensical
https://zensical.org/docs/get-started/
https://zensical.org/docs/publish-your-site/
https://mermaid.ai/open-source/intro/index.html
https://arc42.org/
https://github.com/arc42/arc42-template/tree/master/EN
https://diataxis.fr/
https://github.com/evildmp/diataxis-documentation-framework



Afterwards, review the current copilot, codex, python instructions and revalidate the tooling loop for changes. 
Derive a plan first and refactor aggressively.
--
DONE:
Reference: [https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex](https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex)
Optimize the following activity for a /goal oriented workflow for the ddon-dwarf-reconstructor:

Consider the following views on documentation and extract valuable principles to enhance our setup:
arc42 tips/best practices:
https://www.innoq.com/en/blog/2022/01/principles-of-technical-documentation/
https://arc42.org/documentation/
https://docs.arc42.org/home/ -> https://github.com/arc42/docs.arc42.org-site/
https://docs.arc42.org/keywords/
https://faq.arc42.org/home/
https://www.innoq.com/en/blog/2022/08/brief-introduction-to-arc42/
diataxis opinion pieces:
https://emmanuelbernard.com/blog/2024/12/19/diataxis/
https://blog.sequinstream.com/we-fixed-our-documentation-with-the-diataxis-framework/
Foundation for our own custom instructions:
https://github.com/github/awesome-copilot/blob/main/skills/documentation-writer/SKILL.md
https://github.com/github/awesome-copilot/blob/main/agents/se-technical-writer.agent.md
https://github.com/github/awesome-copilot/blob/main/agents/project-documenter.agent.md


Afterwards, review the current copilot, codex, and custom instructions. Derive a new tone, style and instructions for reuse whenever documentation is created. Make sure we always stick to arc42+Diataxis for our overall documentation in the repository.
Derive or update docs.
Derive a plan first and refactor aggressively.
--
DONE:
Migrate langfuse and sonarqube docs to developer-focused how-tos and/or crosscutting concepts sections https://docs.arc42.org/section-8/
Also, continue to scan the source code and refine the docs incrementally until there are no gaps
Be thorough and detailed, include UML and other useful architectural diagrams, e.g. follow the C4 model: https://c4model.com/, https://c4model.com/introduction, https://c4model.com/abstractions, https://c4model.com/diagrams, https://mermaid.ai/open-source/syntax/c4.html
Mermaid best practices:
https://handbook.gitlab.com/handbook/tools-and-tips/mermaid/
https://mermaid.ai/open-source/intro/syntax-reference.html
Pursue the publication end-to-end incl. committing, pushing, opening a PR
Involve me when you really can't execute a settings change in GitHub yourself and are blocked
/Goal: Don't stop until you can verify the new GitHub page is available on the web
--
DONE:
Install and use mermaid-cli and/or mermaid-lint to validate diagrams:
https://github.com/jasonworden/mermaid-lint
https://pypi.org/project/mermaid-cli/
https://github.com/mermaid-js/mermaid-cli
Do the same for markdown:
https://github.com/markdownlint/markdownlint
https://github.com/davidanson/markdownlint
https://github.com/DavidAnson/markdownlint-cli2
--
DONE:

Instead of Neo4j, evaluate ladybugdb which follows a leaner approach similar to SQLite and provides a Python integration and CLI/uv support. Update the specs.

https://theconsensus.dev/p/2026/05/29/ladybug-duckdb-and-postgresql.html
https://volodymyrpavlyshyn.medium.com/hybrid-graph-rag-with-ladybugdb-when-vectors-meet-graphs-aa7ddec45632
https://docs.ladybugdb.com/installation/
https://docs.ladybugdb.com/tutorials/python/
https://ladybugdb.com/
https://docs.ladybugdb.com/
https://github.com/LadybugDB/ladybug
https://docs.ladybugdb.com/tutorials/python/
https://docs.ladybugdb.com/import/graph-databases/
--
DONE:
Reference: [https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex](https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex)
Optimize the following activity for a /goal oriented workflow for the ddon-dwarf-reconstructor:

Profile the application. The goal for now is collecting metrics and evidence for CPU, RAM, I/O behavior and method-level traces. Check the references and identify the best and most modern tooling setup. Derive a reusable pattern for the future whenever we want to profile the application again, e.g. via "performance"/profiling tests that can be run via just/pytest or some tooling. Make sure benchmark data is historized for periodic checks. It might make sense to build a small SQLite database specifically for that.
https://daily.dev/blog/top-7-python-profiling-tools-for-performance/
https://docs.python.org/3/library/profile.html
https://github.com/joerick/pyinstrument
https://docs.nersc.gov/development/languages/python/profiling-debugging-python/
https://realpython.com/python-profiling/
https://researchcomputing.princeton.edu/python-profiling
https://rse.shef.ac.uk/pando-python/index.html
https://github.com/python/pyperformance
https://locust.io/
https://www.browserstack.com/guide/python-performance-testing
https://blog.sentry.io/python-performance-testing-a-comprehensive-guide/

Afterwards, review the current copilot, codex, python instructions and revalidate the tooling loop for changes. Update documentation, specs and the knowledge base.
Derive a plan first and refactor the code aggressively.
--
DONE:
Re-evaluate our Nuitka integration and setup. Compare the performance with and without (as tool). Do we still have a benefit with Nuitka? Also check on the free-threaded version of Python and also perform a performance comparison. Would that also still be compatible with Nuitka? Do we have any dependencies that fail due to this?
https://nuitka.net/user-documentation/nuitka-package-config.html
https://nuitka.net/user-documentation/performance.html
https://nuitka.net/user-documentation/tips.html
https://nuitka.net/user-documentation/tutorial-setup-and-build.html
https://nuitka.net/user-documentation/user-manual.html
Also check for potential FFI benefits for hotpaths using Rust:
https://github.com/pyo3/pyo3
https://blog.serghei.pl/posts/a-quick-dive-into-ffi-in-python/
--
DONE:
Optimize the following activity for a /goal oriented workflow for the ddon-dwarf-reconstructor:

Evaluate based on the profiling traces ways to optimize our code. If they are missing, generate function/line traces to analyze.
Are we using the right algorithms?
The goal should be to run a thorough analysis until we are certain we have found fitting algorithms and approaches. Then to incrementally implement these, check for regressions and benchmark performance. Separate between tweaking Python code vs. algorithmic improvements.

Check this prior analysis with citations:
D:\ddon-dwarf-reconstructor\algorithmandperformanceresearch.md



Non exhaustive list of additional resources:
https://wiki.python.org/moin/PythonSpeed/PerformanceTips
https://blog.jetbrains.com/pycharm/2025/11/10-smart-performance-hacks-for-faster-python-code/
https://blog.appsignal.com/2025/05/28/ways-to-optimize-your-code-in-python.html
https://blog.easecloud.io/cloud-infrastructure/learn-python-performance-optimization/
https://realpython.com/ref/best-practices/optimization/

Graph-related
https://memgraph.com/docs/advanced-algorithms/deep-path-traversal
https://www.geeksforgeeks.org/dsa/graph-data-structure-and-algorithms/
https://neo4j.com/blog/graph-data-science/graph-algorithms/
https://en.wikipedia.org/wiki/Category:Graph_algorithms
https://memgraph.com/blog/graph-algorithms-applications

AST-related
https://www.dropstone.io/blog/ast-parsing-tree-sitter-40-languages
https://www.envisioning.com/vocab/ast-abstract-syntax-tree
https://bookish.press/hcpl/chapter7
https://medium.com/@jouryjc0409/ast-enables-code-rag-models-to-overcome-traditional-chunking-limitations-b0bc1e61bdab
https://en.wikipedia.org/wiki/Abstract_syntax_tree
https://en.wikipedia.org/wiki/Recursive_descent_parser
--
DONE:
Reference: https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex
Optimize the following activity for a /goal oriented workflow for the ddon-dwarf-reconstructor:
Goal 1: Perform a thorough research and investigation into tooling and databases. Understand DWARF format and DWARF tools in other projects. Figure out how to map what we understand into a columnar, analytical database structure along with dimensional modelling
Goal 2: Derive a usable data model, incrementally verify hypotheses and ensure our header files can still be generated correctly based on the data needed for rLayout.
Goal 3: Perform a new performance benchmark. Traverse all CUs once, convert all DWARF data into table-compatible rows based on the schema we derived. Load everything into Apache Doris with appropriate performance optimizations like indexes. Use modern table formats like Apache Iceberg and storage formats like Apache Parquet via analytical modelling techniques for data lake(houses).
CU traversal is the single most expensive operation but also the single most important one. Missing CUs lead to wrong/missing data. It is unavoidable. Turn this into a "big data" or analytical problem where looking for something like rLayout becomes a query instead. Parquet file format which has zstd support as well. Review what we know about DWARF and the structures used in our current library or in LLVM to derive useful data types, relationships, nestedness etc. derive useful technical and functional keys and decide where to fan out in the data model and what to pre-compute.
Tool references:
https://llvm.org/docs/CommandGuide/llvm-dwarfutil.html
https://llvm.org/docs/CommandGuide/llvm-dwarfdump.html
https://llvm.org/docs/CommandGuide/dsymutil.html
llvm/llvm-project / D:\llvm-project
https://github.com/llvm/llvm-project/tree/main/llvm/lib/DebugInfo/DWARF
Analytical data:
https://openmetal.io/resources/blog/building-a-modern-data-lake-using-open-source-tools/
https://www.alation.com/blog/data-lake-architecture-guide/
https://www.phdata.io/blog/what-are-the-best-data-modeling-methodologies-processes-for-my-data-lake/
https://www.min.io/blog/the-architects-guide-a-modern-datalake-reference-architecture
https://www.databricks.com/blog/data-modeling-best-practices-implementation-modern-lakehouse
apache/parquet-format
apache/arrow
apache/iceberg
apache/doris
Our lib:
https://github.com/eliben/pyelftools/tree/main / D:\pyelftools -> we were recently using version 0.32, since May there is now 0.33 -> it is worth re-investigating the APIs
https://github.com/eliben/pyelftools/blob/main/elftools/dwarf/compileunit.py
https://github.com/eliben/pyelftools/blob/main/elftools/dwarf/die.py
Related ideas but mostly for structural reference for the data model:
https://github.com/volatilityfoundation/dwarf2json
https://github.com/yurydelendik/dwarf-to-json
Afterwards, review the current instructions, revalidate the tooling loop for changes.
Derive a plan first and refactor aggressively, disregard breaking changes.
Make sure to use llvm-dwarfdump via msys2 UCRT profile C:\msys64\ucrt64.exe
As far as I can tell sony doesn't have custom DWARF extensions and LLVM is more reliable. THe original PS4 Clang toolchain is old and not as good at parsing DWARF.
I don't care about initial RAM usage, I have 64GB of RAM. It's acceptable for initial dumping to take up resources. The memory boundedness was valid for the previous architecture where we would use pyelf ad-hoc. But we should get away from this and rely more on the ad-hoc Doris queries instead.
Avoid Disk E as it is an external portable HDD.
Stick to Disk C by utilizing AppData/Local/temp the default temp storage
Criticially challenge: do we really need JSON as intermediary? It helped us build a structure. But Doris requires analytical/dimensional modelling to be effective. We want to use the full extent of data lake engines, but these require properly serialized table data. Why use JSON as intermediate instead of directly inserting into the DB?
Check out and use these Apache Doris skills, they should help in designing the tables and architecture along with apache/doris-cli
apache/doris-skills
https://doris.apache.org/community/source-install/compilation-win
https://doris.apache.org/docs/3.x/table-design/data-type
I have installed rustup and compiled the doris-cli here: D:\doris-cli\target\release
Investigate the following references and how they can further support our setup and ensure we are using latest versions before continuing our investigation:
Docker compose setup samples:
https://github.com/apache/doris/tree/master/docker/runtime/docker-compose-demo
https://github.com/apache/doris/tree/master/docker/runtime/doris-compose
https://github.com/apache/doris/tree/master/docker/runtime
Arrow: -> v25.0.0 & Are we applying all best practices?
https://arrow.apache.org/docs/python/index.html
https://arrow.apache.org/cookbook/py/
https://pypi.org/project/pyarrow/
Iceberg: -> v0.11.1
https://py.iceberg.apache.org/
https://github.com/apache/iceberg-python
https://motherduck.com/glossary/pyiceberg/
Doris: -> v4.1.3 SQL Alchemy+Custom DORIS client vs. Doris MySQL or Doris Arrow flight sql?
https://pypi.org/project/PyMySQL/ PyMySQL -> v1.2.0
https://pypi.org/project/SQLAlchemy/ SQLAlchemy -> v2.0.51
https://pypi.org/project/pydoris/
https://doris.apache.org/docs/4.x/connection-integration/arrow-flight-sql -> evaluate for performance
https://doris.apache.org/docs/4.x/connection-integration/mysql-proto
Doris optimization techniques: Are we squeezing everything out that we can from the engine/technology?
https://doris.apache.org/docs/4.x/query-acceleration/optimization-technology-principle/query-optimizer
https://doris.apache.org/docs/4.x/query-acceleration/query-profile
https://doris.apache.org/docs/4.x/query-acceleration/materialized-view/intro-link
https://doris.apache.org/docs/4.x/query-acceleration/tuning/tuning-plan/schema-and-index-optimization
https://doris.apache.org/docs/4.x/query-acceleration/performance-tuning-overview/tuning-overview
https://doris.apache.org/docs/4.x/query-acceleration/optimization-technology-principle/statistics
https://doris.apache.org/docs/4.x/lakehouse/best-practices/doris-iceberg
https://doris.apache.org/docs/4.x/table-design/overview
https://doris.apache.org/docs/4.x/data-operate/import/load-manual
https://doris.apache.org/docs/4.x/query-data/mysql-compatibility
https://doris.apache.org/docs/4.x/query-acceleration/tuning/tuning-plan/dml-tuning-plan
We know that the full traversal technically works. But it has been running for hours. Are we sure the schema is correct and useful and usable and will help us in improving performance? We should not attempt to loop this potential 12h process unless we are sure the schema is what we need, because then checking back on improvements will also be a very long process. Is it possible to run some queries right now and perform simple performance sanity checks while it is continuing to write?
--
DONE:
Investigate the following references and how they can further support our setup and ensure we are using latest versions before continuing our investigation:
Arrow: -> v25.0.0 & Are we applying all best practices?
https://arrow.apache.org/docs/python/index.html
https://arrow.apache.org/cookbook/py/
https://pypi.org/project/pyarrow/
Doris: -> v4.1.3 SQL Alchemy+Custom DORIS client vs. Doris MySQL or Doris Arrow flight sql?
https://pypi.org/project/PyMySQL/ PyMySQL -> v1.2.0
https://pypi.org/project/SQLAlchemy/ SQLAlchemy -> v2.0.51
https://pypi.org/project/pydoris/
https://doris.apache.org/docs/4.x/connection-integration/arrow-flight-sql -> evaluate for performance
https://doris.apache.org/docs/4.x/connection-integration/mysql-proto
--
DONE:
Make sure our DB is fully optimized using Doris skills and CLI
https://github.com/apache/doris-skills
https://github.com/apache/doris-cli
Use our benchmarking tooling with Scalene and trace methods/lines for CPU usage before drawing any conclusions what to optimize.
--
DONE:
Goal: Create a new very simple Python Docker container to run the reconstructor and local volume mount the output and other logging/debugging files. This should allow us to verify Linux compatibility and make Scalene hopefully work with line output - as this seems to be a CPython Windows bug.
And afterwards profile the runtime and derive action items based on the observations via py-spy and other tools.
Check: https://hub.docker.com/_/python
Since we are using uv for everything, there seem to be specific Docker instructions for that. Consider this as well: https://docs.astral.sh/uv/guides/integration/docker/#getting-started
https://hub.docker.com/r/astral/uv
https://github.com/astral-sh/uv-docker-example
Explore the scalene command line and compare if a certain set of configurations would help with the issue of missing data. Optimize the setup. Check the source code and readme here:
https://github.com/plasma-umass/scalene
% scalene --help
Scalene: a high-precision CPU and memory profiler, version 1.5.51 (2025.01.29)
https://github.com/plasma-umass/scalene
Consider that maybe we want an optional view on our libraries in case we want to look for faster alternatives or want to change/reimplement an algorithm from a library ourselves. Especially when it seems like from absolute numbers that our code is not at fault. Additionally, I want to check the experimental memory leak detector. Activate it and see what it says.
Also challenge whether we should still keep cProfile if scalene is working now properly. As far as I understand py-spy is useful as it can capture in-process snapshots.
--
DONE:
Upgrade uv to 0.12.3 everywhere, update Python to 3.14.7 everywhere and use the 3.14.7-slim-trixie image for the new container.
https://blog.python.org/2026/08/python-3147-31315/
https://github.com/astral-sh/uv/releases
Also in general check if any other of our dependencies can be upgraded.
Check out these resources if we can improve our uv setup:
https://docs.astral.sh/uv/concepts/projects/sync/#checking-the-lockfile
https://docs.astral.sh/uv/concepts/projects/workspaces/#getting-started
https://docs.astral.sh/uv/concepts/projects/dependencies/#git
https://docs.astral.sh/uv/concepts/build-backend/#choosing-a-build-backend
https://docs.astral.sh/uv/reference/settings/#conflicts
--
DONE:
Evaluate usage of Arrow Flight SQL instead of the MySQL pathway to access Doris. Thoroughly analyze and understand the source material:
https://doris.apache.org/docs/4.x/connection-integration/arrow-flight-sql
https://github.com/apache/doris/issues/25514
https://arrow.apache.org/docs/format/FlightSql.html
https://arrow.apache.org/docs/format/Flight.html
https://arrow.apache.org/blog/2019/10/13/introducing-arrow-flight/
https://arrow.apache.org/cookbook/py/flight.html
https://arrow.apache.org/docs/python/flight.html
https://arrow.apache.org/adbc/main/python/driver_manager.html
https://arrow.apache.org/adbc/main/python/api/adbc_driver_flightsql.html
https://arrow.apache.org/adbc/main/python/recipe/flight_sql.html
https://arrow.apache.org/adbc/main/python/recipe/driver_manager.html
In our case we are just a client while Doris is the SQL Flight Server. I think it would be beneficial to avoid the unnecessary translation layer of MySQL. But it needs to be checked/verified/benchmarked since we are ultimately interested in single records / arrays of records. Maybe this path would only be useful if we also adapted our logic with some map/reduce patterns or other aggregations when deduplicating valid usages of a DIE.
Goal: Get the benchmark working.
Debug the container setup. I currently only see port 8030 + 9030 on FE and 8040 on BE being exposed and the containers are 14h old.
Check back again with these resources:
https://doris.apache.org/docs/4.x/connection-integration/arrow-flight-sql
https://doris.apache.org/blog/arrow-flight-sql-in-apache-doris-for-10x-faster-data-transfer
https://github.com/apache/doris/blob/master/samples/arrow-flight-sql/python/test.py
https://dzone.com/articles/arrow-flight-sql-data-transfer
https://alexmerced.blog/blog/2026-08-06-arrow-flight-adbc-explained.html
--
TODO:
Evaluate Doris optimization techniques: Are we squeezing everything out that we can from the engine/technology?
https://doris.apache.org/docs/4.x/query-acceleration/optimization-technology-principle/query-optimizer
https://doris.apache.org/docs/4.x/table-design/index/index-overview
https://doris.apache.org/docs/4.x/query-acceleration/query-profile
https://doris.apache.org/docs/4.x/query-acceleration/materialized-view/intro-link
https://doris.apache.org/docs/4.x/query-acceleration/tuning/tuning-plan/schema-and-index-optimization
https://doris.apache.org/docs/4.x/query-acceleration/performance-tuning-overview/tuning-overview
https://doris.apache.org/docs/4.x/query-acceleration/optimization-technology-principle/statistics
https://doris.apache.org/docs/4.x/table-design/overview
https://doris.apache.org/docs/4.x/query-data/complex-type
https://doris.apache.org/docs/4.x/query-data/lateral-view
https://doris.apache.org/docs/4.x/query-data/subquery
https://doris.apache.org/docs/4.x/query-data/multi-dimensional-analytics
https://doris.apache.org/docs/4.x/query-data/cte
https://doris.apache.org/docs/4.x/table-design/data-model/tips
https://doris.apache.org/docs/4.x/data-operate/import/load-manual
https://doris.apache.org/docs/4.x/query-data/mysql-compatibility
https://doris.apache.org/docs/4.x/query-acceleration/tuning/tuning-plan/dml-tuning-plan

Here is the plan outlining the approach, incorporate our new benchmarking pathways including rAIFSM which is one of the most heavy workloads:
# Doris 4.x Optimization Evaluation

## Summary

Verdict: the canonical DWARF serving path is well-designed, but Doris is not fully exhausted.

Already strong:

- `DUPLICATE KEY` preserves exact DWARF evidence.
- Source/unit-first keys and hash distribution prune source-scoped queries to 1/16 tablets.
- Inverted indexes, Bloom filters, predicate pushdown, column pruning, and lazy materialization are working.
- Nereids is active; profiled queries show no spills and healthy tablet skew.
- `rLayout` returned 145 rows from a 35.7M-row index in a warm 51 ms profile.

The main remaining opportunity is global lookup fan-out: name and method lookups still touch all tablets. The current `rLayout` and method queries use 8/8 tablets despite returning very few rows. The optimizer is therefore reducing row work, but not tablet scheduling/fan-out. This aligns with Doris guidance to evaluate schema, indexes, and profiles together rather than relying on `EXPLAIN` alone ([optimizer](https://doris.apache.org/docs/4.x/query-acceleration/optimization-technology-principle/query-optimizer), [indexes](https://doris.apache.org/docs/4.x/table-design/index/index-overview), [profiles](https://doris.apache.org/docs/4.x/query-acceleration/query-profile)).

## Key decisions

| Area | Decision |
|---|---|
| Canonical table model | Keep `DUPLICATE KEY`, source-first keys, current distribution, and one-partition design. Do not globally reorder the base tables or use Unique/Aggregate models. |
| Global lookups | Benchmark an explicit source-bound name lookup table sorted by `(source_id, name, unit_offset, die_offset)`. Add a target-offset method table only if the query trace justifies it. Do not alter the canonical tables. |
| Materialized views | Do not add an asynchronous MV to the canonical path. An explicit auxiliary table is easier to bind to the immutable manifest and validate exactly. Test a synchronous MV only as a comparison variant ([materialized views](https://doris.apache.org/docs/4.x/query-acceleration/materialized-view/overview/)). |
| Statistics | Replace broad all-column analysis on wide tables with selective analysis of key/filter columns, then wait for terminal `SHOW ANALYZE` states. Current automatic analysis history contains memory-limit failures even though manual statistics later succeeded ([statistics](https://doris.apache.org/docs/4.x/query-acceleration/optimization-technology-principle/statistics)). |
| Index budget | Measure whether the attribute/name-table inverted indexes and Bloom filters on already-keyed or constant columns justify their storage and load cost. Retain them only when profiles demonstrate value. |
| Storage format | Keep V2/ZSTD initially. V3 and row store are low-priority variants: V3 targets very wide tables, while row store targets high-concurrency `SELECT *` workloads ([storage format](https://doris.apache.org/docs/4.x/table-design/storage-format/), [row store](https://doris.apache.org/docs/4.x/table-design/row-store/)). |
| Loading | Benchmark Stream Load with 1/2/4/8 workers and Doris Streamloader. Do not enable group commit blindly; it primarily targets frequent small batches, not this immutable bulk publication ([load manual](https://doris.apache.org/docs/4.x/data-operate/import/load-manual/), [group commit](https://doris.apache.org/docs/4.x/data-operate/import/group-commit-manual/)). |
| SQL/query features | CTEs, subqueries, lateral views, complex types, multidimensional aggregation, and MySQL compatibility are not current bottlenecks. The runtime workload is predominantly single-table, parameterized point lookup. |
| Parallelism/cache | Benchmark `parallel_pipeline_task_num` and SQL result cache only against representative traces. Do not change global defaults without profile evidence ([parallelism](https://doris.apache.org/docs/4.x/query-acceleration/tuning/tuning-execution/parallelism-tuning), [SQL cache](https://doris.apache.org/docs/4.x/query-acceleration/sql-cache-manual/)). |

## Implementation and evidence changes

1. Extend the analytical evidence ledger with:

   - complete per-family row counts and source identity;
   - `SHOW TABLE STATS`, `SHOW COLUMN STATS`, `SHOW ANALYZE`, `SHOW AUTO ANALYZE`;
   - tablet count, size, health, and skew;
   - cold/warm p50 and p95 profiles containing scan bytes, scan rows, tablet count, schedule time, operator time, memory, and spills.

2. Benchmark the canonical schema against the name and method lookup candidates. Require exact ordered-result parity, manifest/source binding, and no parser or load diagnostics. Promote a candidate only when it improves representative application latency or scan cost without unacceptable storage/load overhead.

3. Add optional serving-variant identity to the existing registry/manifest evidence. The canonical 14-family row contract remains unchanged.

4. Run controlled physical variants for:

   - Bloom/inverted-index removal;
   - bucket counts on tiny tables;
   - V2 versus V3 on the widest family;
   - ZSTD versus LZ4 only if profiles show CPU-bound scans;
   - Stream Load concurrency.

5. Update the analytical-store specification, measured-evidence ledger, operational README, and architecture/reference documentation with measured results and explicit rejected/not-applicable optimizations.

## Acceptance tests

- Exact row counts, source identity, ordering, and query-result hashes remain unchanged.
- No required analysis job remains failed, cancelled, or unobserved.
- All loaded tablets are `NORMAL`; large-table skew remains acceptable.
- Candidate lookup tables demonstrate measured benefit in the representative query trace, not merely improved `EXPLAIN` output.
- Cold and warm results are reported separately; `--no-cache` is not treated as a full storage-cache eviction.
- Existing repository gates remain required after implementation: `uv run just test-unit`, `uv run just check`, `uv run just test`, `uv run just coverage-ci`, and `uv run just audit`.

## Assumptions

- The current single-FE/single-BE, replication-1 deployment is diagnostic evidence, not proof of production-scale distributed performance.
- No representative production query-volume trace has been supplied; therefore auxiliary tables remain candidates until measured.
- Exact source-bound DWARF evidence takes precedence over convenience features or eventual-consistency optimizations.
- Existing 110%-of-baseline acceptance rules remain unchanged wherever an approved baseline exists.

--
TODO:
Check and optimize the Doris configurations:
[https://doris.apache.org/docs/4.x/admin-manual/workload-management/concurrency-control-and-queuing](https://doris.apache.org/docs/4.x/admin-manual/workload-management/concurrency-control-and-queuing)
[https://doris.apache.org/docs/4.x/admin-manual/config/be-config](https://doris.apache.org/docs/4.x/admin-manual/config/be-config)
[https://doris.apache.org/docs/4.x/admin-manual/config/fe-config](https://doris.apache.org/docs/4.x/admin-manual/config/fe-config)
https://doris.apache.org/docs/4.x/query-acceleration/tuning/tuning-execution/parallelism-tuning
--
DONE:
As part of the benchmarks you should also run explain plans on the queries we send to Doris & profile them. This is especially important in case we change our schema and approach later down the line. Check the following resources:
[https://doris.apache.org/docs/4.x/sql-manual/sql-statements/data-query/EXPLAIN](https://doris.apache.org/docs/4.x/sql-manual/sql-statements/data-query/EXPLAIN)
[https://doris.apache.org/docs/4.x/admin-manual/workload-management/analysis-diagnosis](https://doris.apache.org/docs/4.x/admin-manual/workload-management/analysis-diagnosis)
[https://doris.apache.org/docs/4.x/query-acceleration/query-profile](https://doris.apache.org/docs/4.x/query-acceleration/query-profile)


--
TODO:
Document my agents, mcp, skills via APM:
https://github.com/microsoft/apm
--
TODO:
Ensure we are using the right data modelling techniques:
Data modelling:
https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/
Schema Model,Architecture Pattern,Normalization Level,Join Complexity,Storage Profile,ETL/Ingestion Complexity,Primary Target Use Case,Optimal Architecture Tier
Star Schema,Fact_Table → Dim_Table,Low (Denormalized),O(1) per dimension,High redundancy,Low (Direct Inserts),"High-speed BI dashboards, ad-hoc OLAP querying",Presentation / Data Mart (Gold)
Snowflake Schema,Fact_Table → Dim_Table → Sub_Dim,High (3NF for Dimensions),O(N) per dimension depth,Low redundancy,High (Hierarchical resolution),"Storage-constrained environments, deep hierarchies",Presentation / Data Mart (Gold)
Galaxy Schema,Fact_A & Fact_B → Shared Dim_Table,Mixed (Conformed Dimensions),Variable (Multi-fact joins),Moderate,Very High (Cross-domain integrity),Cross-functional enterprise data warehouse correlation,Enterprise Integration / Data Mart
Data Vault 2.0,Hubs (Keys) → Links (Relations) → Satellites (Context),Extremely High (Raw structural decoupling),O(N) (Massive join overhead for reads),Extremely High (Historical inserts),"Moderate (Parallelized, append-only)","Immutable audit trails, agile ingestion, schema drift resistance",Integration / Enterprise DW (Silver)
Starflake Schema,Hybrid (Flat & Hierarchical mix),Mixed (Selective normalization),Variable,Moderate,Moderate to High,Systems with extreme variations in dimension cardinality,Presentation / Data Mart (Gold)
Columnar Wide-Table,Single flattened table containing all facts and attributes,Zero (Fully Flattened),None (0 Joins),Massive redundancy,High (Pre-computation during ETL pipeline),High-throughput vectorized scans on cloud analytical engines,Presentation (Gold) / External Lakehouse
What is the closest to what we are doing right now? Why did we choose to take that direction? Should we invest in a different modelling scheme considering the capabilites of Dora?