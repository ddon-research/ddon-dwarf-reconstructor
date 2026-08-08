# Compare CPython, Nuitka, and free-threaded Python

Use this guide to answer whether the optional compiled launcher or free-threaded CPython improves
the reconstructor. It is an opt-in environmental measurement. Keep the normal CPython environment
and deterministic integration loop unchanged.

## Prepare the runtimes

The root environment uses regular CPython 3.14.6. Build the optional onefile launcher with the
supported Windows MSVC toolchain; the output goes outside the checkout:

```powershell
uv run just native-build
```

Create a separate free-threaded environment. Do not replace the root `.venv`:

```powershell
$env:UV_PROJECT_ENVIRONMENT = (Join-Path $env:TEMP 'ddon-analytical-dwarf\performance\venvs\ddon-3.14t')
uv sync --frozen --no-dev --python C:\Users\morph\AppData\Roaming\uv\python\cpython-3.14.6+freethreaded-windows-x86_64-none\python.exe
uv pip install --python (Join-Path $env:UV_PROJECT_ENVIRONMENT 'Scripts\python.exe') pyperf==2.10.0 py-spy==0.4.2 pyinstrument==5.1.3
```

Use the venv's `Scripts\python.exe`, not the bare uv-managed base interpreter. The project must be
installed in the selected runtime so the comparison command can validate its import.

## Run the comparison

Use the same ELF, source-bound analytical-store manifest, symbol, and warm state for all variants:

```powershell
uv run ddon-dwarf-reconstructor performance compare-runtimes `
  resources/DDOORBIS.elf `
  --symbol rLayout `
  --nuitka-executable (Join-Path $env:TEMP 'ddon-analytical-dwarf\performance\nuitka\cpython314\ddon-reconstructor-cpython314.exe') `
  --free-threaded-python (Join-Path $env:TEMP 'ddon-analytical-dwarf\performance\venvs\ddon-3.14t\Scripts\python.exe') `
  --dwarf-store (Join-Path $PWD 'output\analytical-dwarf\main\store-<source-sha16>\manifest.json') `
  --build-id ps4-02020005 `
  --iterations 3 `
  --artifact-dir (Join-Path $env:TEMP 'ddon-analytical-dwarf\performance\profiles\runtime-compare')
```

The command records each run in `resources/performance/benchmarks.sqlite3` and prints mean
wall/RSS/I/O deltas relative to regular CPython. It also verifies that the generated output files
have the same aggregate manifest hash. Build time is not included in runtime measurements; the
onefile payload extraction cost is included because it is part of the deployed command.

## Interpret the result

Nuitka is useful here only if the deployed executable's startup/distribution properties justify its
build cost. The measured warm `rLayout` comparison currently shows approximately 2.062 s for
CPython, 2.470 s for the Nuitka onefile, and 2.202 s for free-threaded CPython. Nuitka used less
peak RSS but added onefile extraction writes and was slower for this workload. Free-threaded
CPython used substantially more RSS and was also slower.

The result is workload-specific. Repeat after parser, cache, or Python changes and compare only
like-for-like runtime, source identity, state, machine, and configuration rows.

## Compatibility boundary

Regular CPython 3.14.6 compiles and launches with Nuitka 4.1.3 after the application uses deferred
annotations in the two modules that exposed compiler failures. No custom Nuitka package
configuration file is currently needed: the onefile smoke test and output comparison pass without
data-file or implicit-import overrides.

Free-threaded CPython runs the core application, but the complete profiling environment is not
available because Scalene 2.3.0 fails to link its Windows extension for `cp314t`. pyinstrument
5.1.3 imports but enables the GIL while loading its native `stat_profile` extension, so it is not
valid evidence for a no-GIL run. Nuitka 4.1.3 also fails to compile a minimal free-threaded
program against the current CPython internal APIs.
The official [Nuitka roadmap](https://nuitka.net/changelog/roadmap.html) currently records the
no-GIL variant as unsupported. Treat this as blocked upstream evidence, not as a supported build
target.
