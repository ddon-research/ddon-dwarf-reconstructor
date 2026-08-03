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
WIP:
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
Reference: [https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex](https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex)
Optimize the following activity for a /goal oriented workflow for the ddon-dwarf-reconstructor:

Check the GitHub Actions failures and dependabot PRs and validate the proposed changes:
https://github.com/ddon-research/ddon-dwarf-reconstructor/pulls
https://github.com/ddon-research/ddon-dwarf-reconstructor/actions
Most of the PRs are failing due to the correctness tests: https://github.com/ddon-research/ddon-dwarf-reconstructor/actions/runs/30774416064/job/91567057120?pr=7 & https://github.com/ddon-research/ddon-dwarf-reconstructor/actions/runs/30774416064/workflow?pr=7
--
TODO:
Reference: [https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex](https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex)
Optimize the following activity for a /goal oriented workflow for the ddon-dwarf-reconstructor:

Scan the entire codebase and documentation. Completely revamp the documentation approach. Introduce a wiki-like setup with a knowledge graph. I want to have a static site publishable to GitHub pages. Consider we need functional and technical documentation incl. high-level architecture and low-level solution approaches. Check out the following resources and derive the next best step. I am leaning toward zensical as tool with arc42-style docs for architecture and an overarching diataxis-style approach. Diagrams and visualizations should be generated with an as-code approach using mermaid. Not sure if flint fits in anywhere yet. Our specs should serve as a roadmap. Identify gaps, fill them based on the source code analysis and how things currently work and throw away all obsolete documentation.
https://github.com/zensical/zensical
https://zensical.org/docs/get-started/
https://zensical.org/docs/publish-your-site/
https://mermaid.ai/open-source/intro/index.html
https://arc42.org/
https://github.com/arc42/arc42-template/tree/master/EN
https://diataxis.fr/
https://github.com/evildmp/diataxis-documentation-framework

Afterwards, review the current copilot, codex, python instructions and revalidate the tooling loop for changes. Update documentation, specs and the knowledge base.
Derive a plan first and refactor the code aggressively.
--
TODO:
Reference: [https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex](https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex)
Optimize the following activity for a /goal oriented workflow for the ddon-dwarf-reconstructor:

Profile the application. The goal for now is collecting metrics and evidence. Check approaches outlined here and derive an action plan and a reusable pattern for the future whenever we want to profile the application again. Derive new specs based on the findings:
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