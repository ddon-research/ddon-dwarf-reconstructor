<#!
.SYNOPSIS
    Captures the MSVC validation build for SonarQube C/C++ analysis.

.DESCRIPTION
    Resolves the installed Visual Studio C++ toolchain, runs the existing MSVC
    validation command through Sonar's Windows Build Wrapper, and verifies that
    the wrapper produced a compilation database containing C++ translation units.

.PARAMETER BuildWrapperPath
    Full path to build-wrapper-win-x86-64.exe. If omitted, the script searches
    PATH and the default per-user SonarSource installation directory.

.PARAMETER OutputDirectory
    Directory where Sonar Build Wrapper writes compile_commands.json. The default
    is the ignored output/msvc-header-validation-20260801/sonar-build-wrapper path.

.PARAMETER ValidationDirectory
    Directory containing the existing MSVC validation command. The default is
    output/msvc-header-validation-20260801.

.PARAMETER ValidationScript
    Batch file to run from ValidationDirectory. The default is compile_msvc.cmd.

.PARAMETER ValidateOnly
    Resolve and validate the local toolchain without running the wrapped build.

.PARAMETER AllowValidationFailure
    Continue to validate and report the compilation database when the wrapped
    validation command returns a nonzero exit code. Use this only for analysis
    capture when the generated headers have known compile failures.

.EXAMPLE
    .\scripts\sonar\prepare-msvc-analysis.ps1 -ValidateOnly

.EXAMPLE
    .\scripts\sonar\prepare-msvc-analysis.ps1 `
        -BuildWrapperPath "$env:LOCALAPPDATA\SonarSource\build-wrapper-win-x86\build-wrapper-win-x86\build-wrapper-win-x86-64.exe"

.NOTES
    Sonar Build Wrapper output contains environment information and must remain
    local. Do not commit the wrapper binary or generated compilation database.
#>

[CmdletBinding()]
param(
    [Parameter()]
    [string]$BuildWrapperPath,

    [Parameter()]
    [string]$OutputDirectory,

    [Parameter()]
    [string]$ValidationDirectory,

    [Parameter()]
    [string]$ValidationScript = 'compile_msvc.cmd',

    [Parameter()]
    [switch]$ValidateOnly,

    [Parameter()]
    [switch]$AllowValidationFailure
)

$ErrorActionPreference = 'Stop'

function Resolve-ExistingFile {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string]$Path,

        [Parameter(Mandatory)]
        [string]$Description
    )

    $resolvedPath = Resolve-Path -LiteralPath $Path -ErrorAction SilentlyContinue
    if ($null -eq $resolvedPath -or -not (Test-Path -LiteralPath $resolvedPath.Path -PathType Leaf)) {
        throw "Could not find $Description at '$Path'."
    }

    return $resolvedPath.Path
}

function Resolve-ExistingDirectory {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string]$Path,

        [Parameter(Mandatory)]
        [string]$Description
    )

    $resolvedPath = Resolve-Path -LiteralPath $Path -ErrorAction SilentlyContinue
    if ($null -eq $resolvedPath -or -not (Test-Path -LiteralPath $resolvedPath.Path -PathType Container)) {
        throw "Could not find $Description at '$Path'."
    }

    return $resolvedPath.Path
}

function Get-BuildWrapperFile {
    [CmdletBinding()]
    param(
        [Parameter()]
        [string]$RequestedPath
    )

    if (-not [string]::IsNullOrWhiteSpace($RequestedPath)) {
        return Resolve-ExistingFile -Path $RequestedPath -Description 'Sonar Build Wrapper'
    }

    $candidates = [System.Collections.Generic.List[string]]::new()
    $pathCommand = Get-Command -Name 'build-wrapper-win-x86-64.exe' -CommandType Application `
        -ErrorAction SilentlyContinue
    if ($null -ne $pathCommand) {
        $candidates.Add($pathCommand.Source)
    }

    if (-not [string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) {
        $candidates.Add((Join-Path $env:LOCALAPPDATA `
            'SonarSource\build-wrapper-win-x86\build-wrapper-win-x86\build-wrapper-win-x86-64.exe'))
    }

    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    throw 'Sonar Build Wrapper was not found. Use -BuildWrapperPath with build-wrapper-win-x86-64.exe.'
}

function Get-VisualStudioDeveloperCommandFile {
    [CmdletBinding()]
    param()

    $programFilesX86 = ${env:ProgramFiles(x86)}
    if ([string]::IsNullOrWhiteSpace($programFilesX86)) {
        throw 'The Program Files (x86) environment variable is not available.'
    }

    $vswherePath = Join-Path $programFilesX86 'Microsoft Visual Studio\Installer\vswhere.exe'
    $vswherePath = Resolve-ExistingFile -Path $vswherePath -Description 'Visual Studio installer locator'
    $vswhereOutput = & $vswherePath -latest -products * `
        -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
    $vswhereExitCode = $LASTEXITCODE
    if ($vswhereExitCode -ne 0) {
        throw "vswhere.exe failed with exit code $vswhereExitCode."
    }

    $installationPath = @($vswhereOutput | Select-Object -First 1) -join ''
    $installationPath = $installationPath.Trim()
    if ([string]::IsNullOrWhiteSpace($installationPath)) {
        throw 'vswhere.exe found no Visual Studio installation with the C++ x64 toolchain.'
    }

    return Resolve-ExistingFile `
        -Path (Join-Path $installationPath 'Common7\Tools\VsDevCmd.bat') `
        -Description 'Visual Studio developer command file'
}

function Test-MsvcToolchain {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string]$DeveloperCommandFile
    )

    $probeCommand = 'call "' + $DeveloperCommandFile + '" -arch=x64 && where cl'
    $probeOutput = & cmd.exe /d /s /c $probeCommand 2>&1
    $probeExitCode = $LASTEXITCODE
    if ($probeExitCode -ne 0) {
        throw "Visual Studio x64 developer environment could not resolve cl.exe. Output: $probeOutput"
    }

    $compilerPath = @($probeOutput | Where-Object { $_ -match '\\cl\.exe$' } | Select-Object -First 1) -join ''
    if ([string]::IsNullOrWhiteSpace($compilerPath)) {
        throw "The Visual Studio x64 developer environment did not report cl.exe. Output: $probeOutput"
    }

    return $compilerPath.Trim()
}

$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
if ([string]::IsNullOrWhiteSpace($ValidationDirectory)) {
    $ValidationDirectory = Join-Path $repositoryRoot 'output\msvc-header-validation-20260801'
} elseif (-not [System.IO.Path]::IsPathRooted($ValidationDirectory)) {
    $ValidationDirectory = Join-Path $repositoryRoot $ValidationDirectory
}
$ValidationDirectory = Resolve-ExistingDirectory `
    -Path $ValidationDirectory -Description 'MSVC validation directory'

$validationScriptPath = Join-Path $ValidationDirectory $ValidationScript
$validationScriptPath = Resolve-ExistingFile -Path $validationScriptPath -Description 'MSVC validation command'

if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $ValidationDirectory 'sonar-build-wrapper'
} elseif (-not [System.IO.Path]::IsPathRooted($OutputDirectory)) {
    $OutputDirectory = Join-Path $repositoryRoot $OutputDirectory
}
$OutputDirectory = [System.IO.Path]::GetFullPath($OutputDirectory)

$wrapperPath = Get-BuildWrapperFile -RequestedPath $BuildWrapperPath
$developerCommandFile = Get-VisualStudioDeveloperCommandFile
$compilerPath = Test-MsvcToolchain -DeveloperCommandFile $developerCommandFile

if ($ValidateOnly.IsPresent) {
    [pscustomobject]@{
        BuildWrapperPath       = $wrapperPath
        DeveloperCommandFile   = $developerCommandFile
        CompilerPath           = $compilerPath
        ValidationScript        = $validationScriptPath
        OutputDirectory         = $OutputDirectory
        ValidationOnly          = $true
    }
    return
}

New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
$wrapperArguments = @(
    '--out-dir',
    $OutputDirectory,
    'cmd.exe',
    '/d',
    '/c',
    'call',
    $developerCommandFile,
    '-arch=x64',
    '&&',
    'cd',
    '/d',
    $ValidationDirectory,
    '&&',
    'call',
    $validationScriptPath
)
& $wrapperPath @wrapperArguments
$wrapperExitCode = $LASTEXITCODE
if ($wrapperExitCode -ne 0 -and -not $AllowValidationFailure.IsPresent) {
    throw "Sonar Build Wrapper or the MSVC validation command failed with exit code $wrapperExitCode."
}
if ($wrapperExitCode -ne 0) {
    Write-Warning "The wrapped MSVC validation command failed with exit code $wrapperExitCode; validating the captured database anyway."
}

$compileCommandsPath = Join-Path $OutputDirectory 'compile_commands.json'
$compileCommandsPath = Resolve-ExistingFile `
    -Path $compileCommandsPath -Description 'Sonar compilation database'
$compileCommands = @(Get-Content -LiteralPath $compileCommandsPath -Raw | ConvertFrom-Json)
$translationUnits = @(
    $compileCommands | Where-Object {
        $_.file -match '\.(c|cc|cpp|cxx)$'
    }
)
if ($translationUnits.Count -eq 0) {
    throw "The compilation database contains no C/C++ translation-unit entries: '$compileCommandsPath'."
}
$msvcFlagEntries = @(
    $translationUnits | Where-Object {
        $compileArguments = if ($null -ne $_.arguments) {
            $_.arguments -join ' '
        } else {
            $_.command
        }
        $compileArguments -match '/std:c\+\+latest' -and
            $compileArguments -match '/EHsc' -and
            $compileArguments -match '/W4' -and
            $compileArguments -match '/Zc:__cplusplus'
    }
)
if ($msvcFlagEntries.Count -eq 0) {
    throw "The compilation database contains no translation unit with the expected MSVC flags."
}

$result = [pscustomobject]@{
    BuildWrapperPath       = $wrapperPath
    CompileCommandsPath     = $compileCommandsPath
    CompilerPath            = $compilerPath
    TranslationUnitCount    = $translationUnits.Count
    MsvcFlagEntryCount      = $msvcFlagEntries.Count
    ValidationExitCode      = $wrapperExitCode
    ValidationOnly          = $false
}
$result
if ($AllowValidationFailure.IsPresent) {
    exit 0
}
