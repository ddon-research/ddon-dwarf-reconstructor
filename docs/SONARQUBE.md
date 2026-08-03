# SonarQube C/C++ Analysis

The repository uses SonarQube for VS Code for local C/C++ analysis of the generated MSVC
validation headers. SonarQube for VS Code requires a compilation database for C and C++ code.
The repository generates the validation translation units and command file, then uses Sonar's
Windows Build Wrapper around that generated Visual Studio x64 command.

## Prerequisites

- SonarQube for VS Code is installed and enabled in VS Code.
- Visual Studio Community 2026 is installed with the MSVC x64 build tools.
- `vswhere.exe` is available at the standard Visual Studio installer location.
- The root uv environment is installed with `uv sync --python 3.14.6`.
- Sonar's Windows Build Wrapper is downloaded outside the repository.

Sonar documents the supported C/C++ environments and compilation-database setup in [Analyze C
and C++ code](https://docs.sonarsource.com/sonarqube-for-vs-code/getting-started/running-an-analysis#analyze-c-and-cpp-code).
Microsoft C/C++ compilers and Windows x86-64 are supported environments.

## Install Build Wrapper

Download the official Windows wrapper into a per-user directory. The wrapper and its generated
environment dump must remain outside source control.

```powershell
$installRoot = Join-Path $env:LOCALAPPDATA 'SonarSource\build-wrapper-win-x86'
$archivePath = Join-Path $env:TEMP 'build-wrapper-win-x86.zip'
New-Item -ItemType Directory -Path $installRoot -Force | Out-Null
Invoke-WebRequest `
    -Uri 'https://sonarcloud.io/static/cpp/build-wrapper-win-x86.zip' `
    -OutFile $archivePath
Expand-Archive -LiteralPath $archivePath -DestinationPath $installRoot -Force
```

The repository Python adapter also searches this default path:

```text
%LOCALAPPDATA%\SonarSource\build-wrapper-win-x86\build-wrapper-win-x86\build-wrapper-win-x86-64.exe
```

## Generate Compilation Database

Run the prerequisite check first:

```text
uv run just sonar-validate
```

Then capture the generated MSVC validation command:

```text
uv run just sonar-capture
```

`prepare_msvc_analysis.py` creates the Sonar inputs from the generated headers in the validation
bundle: one standalone `.cpp` per header, `sonar-inputs.json`, and `compile_msvc.cmd`. The current
setup generated five standalone translation units, and `sonar-capture` produced a validated
five-entry compilation database with MSVC exit code 0. It also writes `translation-units/compile_all.cpp`
as optional aggregate evidence, but the default Sonar wrapper does not compile that aggregate
because the representative headers intentionally repeat declarations across standalone closures.

The database is written to:

```text
output/msvc-header-validation-20260801/sonar-build-wrapper/compile_commands.json
```

The Python adapter resolves the installed Visual Studio instance with `vswhere.exe`, loads the x64
developer environment, and preserves the validation flags used by the repository:

```text
/std:c++latest /EHsc /W4 /Zc:__cplusplus
```

The default command is strict and returns the MSVC build exit code. If generated headers have
known compile failures but a compilation database is still needed for diagnostic analysis, use
the explicit analysis-only mode:

```text
uv run python -m tools.sonar.prepare_msvc_analysis --allow-validation-failure
```

This mode succeeds only after the Build Wrapper has produced a valid JSON database containing at
least one C or C++ translation-unit entry. It reports the original MSVC exit code in its result;
it does not make the generated headers compile or suppress the compiler diagnostics.

To inspect the optional aggregate separately, compile
`output/msvc-header-validation-20260801/translation-units/compile_all.cpp` with the same MSVC
environment and record its diagnostics independently from the Sonar compilation database.

## Activate Analysis in VS Code

Open the repository folder in VS Code after generating the database. SonarQube for VS Code can
detect a `compile_commands.json` file in the opened folder. For the generated database under the
validation output directory, set the full local path in VS Code settings:

```json
{
    "sonarlint.pathToCompileCommands": "D:/ddon-dwarf-reconstructor/output/msvc-header-validation-20260801/sonar-build-wrapper/compile_commands.json"
}
```

Alternatively, use the SonarQube panel action to select the compilation database. Open a generated
C++ translation unit or header and save it to trigger analysis. Issues appear in the editor and in
the Problems panel.

The setting is intentionally not committed to `.vscode`; the output path and Build Wrapper data
contain machine-specific environment information. The generated database and wrapper output are
ignored by the repository's existing `output/` rule.

## Troubleshooting

- **Build Wrapper not found:** pass `--build-wrapper-path` with the full path to
  `build-wrapper-win-x86-64.exe`, for example:
  `uv run python -m tools.sonar.prepare_msvc_analysis --build-wrapper-path D:/tools/build-wrapper-win-x86-64.exe`.
- **MSVC not found:** install the Visual Studio C++ x64 workload and rerun `-ValidateOnly`.
- **No C/C++ entries:** confirm that the validation command compiled at least one `.cpp` file and
  rerun the capture.
- **Generated-header errors:** use strict mode to treat them as build failures. Use
  `--allow-validation-failure` only to inspect the captured commands in SonarQube; resolve the
  generated-header closure issues separately.
- **Stale analysis:** regenerate the database after changing compiler flags, include paths, or
  generated headers, then refresh the active database in the SonarQube panel.
