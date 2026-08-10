# Plan: Nuitka and runtime comparison

1. Inspect the existing `native-build` recipe, locked Nuitka version, entry point, and package
   imports; verify the linked official setup, package configuration, tips, performance, and manual
   guidance.
2. Add typed runtime identity to performance workloads and history, with alternate Python and
   compiled-launcher command construction through the common runner.
3. Replace the implicit compiler choice with the supported Windows MSVC path and publish build
   outputs outside the checkout.
4. Add `performance compare-runtimes`, dependency probes, deterministic-output checks, and tests.
5. Measure warm `rLayout` for CPython, Nuitka, and free-threaded CPython; separately attempt
   free-threaded Nuitka compilation and record the exact blocker.
6. Update the profiling how-to, reference, knowledge base, durable instructions, and static
   history, then run the complete root and nested validation loops.
