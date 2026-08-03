# Implementation plan

1. Inventory the current source, tests, docs navigation, external-tool adapters, Langfuse Compose
   contract, static-site workflow, and repository instruction adapters.
2. Replace the flat Langfuse and SonarQube pages with Diátaxis how-to guides that preserve exact
   commands, safety boundaries, evidence tiers, and source links.
3. Add the arc42 section-8 crosscutting concepts page with C4 component, UML, and sequence views;
   add C4 context/container views to the corresponding architecture pages.
4. Synchronize navigation, architecture index, observability links, writing guidance, roadmap, and
   instruction adapters. Remove obsolete duplicate pages and stale links.
5. Install the locked Node documentation tools, lint authored Markdown, render every Mermaid fence,
   build the site strictly, scan local links and retired paths, run the root quality and nested
   project loops, and repair any documentation drift found by the checks.
6. Commit only intended repository changes on the existing feature branch, push, update PR #13's
   scope/body, inspect checks, and verify the public Pages URL.
