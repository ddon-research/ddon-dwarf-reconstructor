[CmdletBinding()]
param(
    [string]$ComposeFile = (Join-Path $PSScriptRoot "compose.yaml"),
    [string[]]$ComposeOverlay = @(),
    [string]$StoreManifest,
    [string]$EnvFile = (Join-Path $PSScriptRoot ".env"),
    [string]$ImageLockFile = (Join-Path $PSScriptRoot "images.lock.json"),
    [string]$OutputPath,
    [ValidateRange(1, 99)]
    [int]$MinimumFreePercent = 15
)

$ErrorActionPreference = "Stop"

function Read-DotEnv([string]$Path) {
    $values = @{}
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $values
    }
    foreach ($line in Get-Content -LiteralPath $Path) {
        if ($line -match '^\s*(?:export\s+)?([^#=\s]+)\s*=\s*(.*)\s*$') {
            $values[$Matches[1]] = $Matches[2].Trim().Trim('"').Trim("'")
        }
    }
    return $values
}

function Get-DriveReport([string]$Path) {
    $root = [System.IO.Path]::GetPathRoot($Path)
    if ([string]::IsNullOrWhiteSpace($root) -or $root -notmatch '^[A-Za-z]:') {
        return [pscustomobject]@{ path = $Path; drive = $null; status = "unsupported_path" }
    }
    $driveLetter = $root.Substring(0, 1).ToUpperInvariant()
    try {
        $volume = Get-Volume -DriveLetter $driveLetter -ErrorAction Stop
    } catch {
        return [pscustomobject]@{
            path = $Path
            drive = $driveLetter
            status = "volume_unavailable"
            error = $_.Exception.Message
        }
    }
    $freePercent = if ($volume.Size -gt 0) {
        [math]::Round(($volume.SizeRemaining / $volume.Size) * 100, 2)
    } else {
        0
    }
    [pscustomobject]@{
        path = $Path
        drive = $driveLetter
        health = [string]$volume.HealthStatus
        operational_status = [string]$volume.OperationalStatus
        size = [int64]$volume.Size
        size_remaining = [int64]$volume.SizeRemaining
        free_percent = $freePercent
        status = if ($driveLetter -eq "E") { "portable_drive_rejected" }
        elseif ($freePercent -lt $MinimumFreePercent) { "insufficient_headroom" }
        elseif ($volume.HealthStatus -ne "Healthy" -or $volume.OperationalStatus -ne "OK") { "volume_unhealthy" }
        else { "pass" }
    }
}

function Test-DirectoryAccess([string]$Path) {
    $probe = $null
    $readable = $false
    $writable = $false
    $errors = [System.Collections.Generic.List[string]]::new()

    try {
        $entries = @(Get-ChildItem -LiteralPath $Path -File -Force -ErrorAction Stop | Select-Object -First 32)
        $readableEntry = $false
        foreach ($entry in $entries) {
            try {
                $stream = [System.IO.File]::Open(
                    $entry.FullName,
                    [System.IO.FileMode]::Open,
                    [System.IO.FileAccess]::Read,
                    ([System.IO.FileShare]::Read -bor [System.IO.FileShare]::Write -bor [System.IO.FileShare]::Delete)
                )
                try {
                    $buffer = New-Object byte[] 1
                    $null = $stream.Read($buffer, 0, 1)
                } finally {
                    $stream.Dispose()
                }
                $readableEntry = $true
                break
            } catch {
                continue
            }
        }
        $readable = ($entries.Count -eq 0) -or $readableEntry
        if (-not $readable) {
            throw "no sampled file could be opened for read"
        }
    } catch {
        $errors.Add("read: $($_.Exception.Message)")
    }

    try {
        $probe = Join-Path $Path (".ddon-doris-preflight-" + [guid]::NewGuid().ToString("N") + ".tmp")
        $expected = "ddon-doris-preflight"
        [System.IO.File]::WriteAllText($probe, $expected, [System.Text.Encoding]::UTF8)
        $actual = [System.IO.File]::ReadAllText($probe, [System.Text.Encoding]::UTF8)
        if ($actual -ne $expected) {
            throw "temporary access probe did not round-trip its contents"
        }
        $writable = $true
    } catch {
        $errors.Add("write: $($_.Exception.Message)")
    } finally {
        if ($null -ne $probe) {
            Remove-Item -LiteralPath $probe -Force -ErrorAction SilentlyContinue
        }
    }

    [pscustomobject]@{
        readable = $readable
        writable = $writable
        status = if ($readable -and $writable) { "pass" } else { "access_failed" }
        errors = @($errors)
    }
}

$failures = [System.Collections.Generic.List[string]]::new()
$compose = if (Test-Path -LiteralPath $ComposeFile) {
    (Resolve-Path -LiteralPath $ComposeFile).Path
} else {
    [System.IO.Path]::GetFullPath($ComposeFile)
}
$lock = if (Test-Path -LiteralPath $ImageLockFile) {
    (Resolve-Path -LiteralPath $ImageLockFile).Path
} else {
    [System.IO.Path]::GetFullPath($ImageLockFile)
}
$envPath = if (Test-Path -LiteralPath $EnvFile) {
    (Resolve-Path -LiteralPath $EnvFile).Path
} else {
    [System.IO.Path]::GetFullPath($EnvFile)
}
$envValues = Read-DotEnv $EnvFile

if (-not (Test-Path -LiteralPath $compose -PathType Leaf)) { $failures.Add("compose file is missing: $ComposeFile") }
if (-not (Test-Path -LiteralPath $lock -PathType Leaf)) { $failures.Add("image lock is missing: $ImageLockFile") }

$rendered = ""
if ($failures.Count -eq 0) {
    $composeArgs = @("compose", "--env-file", $EnvFile, "-f", $compose)
    foreach ($overlay in $ComposeOverlay) { $composeArgs += @("-f", $overlay) }
    $composeArgs += @("config", "--format", "json")
    $rendered = (& docker @composeArgs 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0) { $failures.Add("docker compose config failed") }
}

$lockedImages = @{}
if (Test-Path -LiteralPath $lock -PathType Leaf) {
    $lockObject = Get-Content -LiteralPath $lock -Raw | ConvertFrom-Json
    foreach ($property in $lockObject.images.PSObject.Properties) {
        $lockedImages[$property.Name] = [string]$property.Value
    }
}

$imageChecks = @()
foreach ($image in @("apache/doris:fe-4.1.3", "apache/doris:be-4.1.3")) {
    $expected = $lockedImages[$image]
    $match = [regex]::Match($rendered, [regex]::Escape($image) + '@(?<digest>sha256:[0-9a-f]{64})')
    $actual = if ($match.Success) { $match.Groups["digest"].Value } else { $null }
    $status = if ($null -eq $expected) { "missing_lock_entry" }
    elseif ($null -eq $actual) { "missing_rendered_digest" }
    elseif ($expected -ne $actual) { "digest_mismatch" }
    else { "pass" }
    if ($status -ne "pass") { $failures.Add("$($image): $status") }
    $imageChecks += [pscustomobject]@{ image = $image; expected_digest = $expected; rendered_digest = $actual; status = $status }
}

if ($rendered -match '(?im)ignore_broken_disk\s*[:=]\s*true') {
    $failures.Add("ignore_broken_disk=true is prohibited")
}

$pathChecks = @()
$servingChecks = [pscustomobject]@{
    fe_connectivity = @{ status = "not_observed" }
    backend_tablet_readiness = @{ status = "not_observed" }
    source_bound_queries = @{ status = "not_observed" }
}
if ($failures.Count -eq 0) {
    . (Join-Path $PSScriptRoot "preflight-storage.ps1")
    $configuration = $rendered | ConvertFrom-Json
    $pathChecks = @(Get-StorageChecks $configuration)
}
$storageStatus = if ($failures.Count -eq 0) { "pass" } else { "fail" }
if ($storageStatus -eq "pass" -and -not [string]::IsNullOrWhiteSpace($StoreManifest)) {
    $sqlPorts = @($configuration.services.'doris-fe'.ports | Where-Object target -EQ 9030)
    if ($sqlPorts.Count -ne 1) {
        $failures.Add("one FE SQL port publication is required")
    } else {
        Push-Location (Join-Path $PSScriptRoot "../..")
        try {
            $servingJson = & uv run --no-sync python -m ddon_dwarf_reconstructor.infrastructure.analytical.doris_readiness `
                --manifest $StoreManifest --sql-port $sqlPorts[0].published
            if ($LASTEXITCODE -ne 0) { $failures.Add("serving readiness failed") }
            if ($servingJson) { $servingChecks = ($servingJson | Out-String) | ConvertFrom-Json }
        } finally { Pop-Location }
    }
}

$report = [pscustomobject]@{
    checked_at = (Get-Date).ToString("o")
    compose_file = $compose
    compose_overlays = $ComposeOverlay
    storage_readiness = $storageStatus
    serving = $servingChecks
    env_file = $envPath
    image_lock_file = $lock
    minimum_free_percent = $MinimumFreePercent
    images = $imageChecks
    paths = $pathChecks
    ignore_broken_disk = "not_enabled_in_rendered_compose"
    status = if ($failures.Count -eq 0) { "pass" } else { "fail" }
    failures = @($failures)
}

$json = $report | ConvertTo-Json -Depth 10
if (-not [string]::IsNullOrWhiteSpace($OutputPath)) {
    $parent = Split-Path -Parent $OutputPath
    if (-not [string]::IsNullOrWhiteSpace($parent)) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
    Set-Content -LiteralPath $OutputPath -Value $json -Encoding UTF8
}
Write-Output $json
if ($failures.Count -gt 0) { exit 1 }
