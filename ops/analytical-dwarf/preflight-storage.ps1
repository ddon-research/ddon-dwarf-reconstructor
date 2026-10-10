# Shared by preflight.ps1. Probe only the resolved effective Compose mounts.
function Get-DockerBackingDrive {
    $settingsPath = Join-Path $env:APPDATA "Docker/settings-store.json"
    if (-not (Test-Path -LiteralPath $settingsPath)) {
        return [pscustomobject]@{ status = "docker_backing_disk_unavailable" }
    }
    $settings = Get-Content -LiteralPath $settingsPath -Raw | ConvertFrom-Json
    $directory = $settings.CustomWslDistroDir
    if ([string]::IsNullOrWhiteSpace($directory)) {
        $directory = Join-Path $env:LOCALAPPDATA "Docker/wsl"
    }
    $disks = @(Get-ChildItem -LiteralPath $directory -Recurse -Filter *.vhdx -ErrorAction SilentlyContinue)
    if ($disks.Count -eq 0) {
        return [pscustomobject]@{ status = "docker_backing_disk_unavailable" }
    }
    $reports = @($disks | ForEach-Object { Get-DriveReport $_.FullName })
    [pscustomobject]@{
        status = if (@($reports | Where-Object status -NE "pass").Count -eq 0) { "pass" } else { "fail" }
        disks = $reports
    }
}

function Test-LinuxVolume([string]$Name, [string]$Image) {
    # Inspect first: docker run must not create an absent recovery volume implicitly.
    $null = & docker volume inspect $Name 2>&1
    if ($LASTEXITCODE -ne 0) { return [pscustomobject]@{ status = "volume_missing"; volume = $Name } }
    $probe = @'
set -eu
p=$(mktemp /probe/.ddon-preflight-XXXXXX)
trap 'rm -f -- "$p"' EXIT
printf 'ddon-storage-probe' > "$p"
sync "$p"
test "$(cat "$p")" = 'ddon-storage-probe'
df -Pk /probe | tail -1
'@
    $output = @(& docker run --rm --network none --entrypoint /bin/sh `
        --mount "type=volume,src=$Name,dst=/probe,volume-nocopy" $Image -c $probe 2>&1)
    if ($LASTEXITCODE -ne 0) {
        return [pscustomobject]@{ status = "linux_access_failed"; volume = $Name; diagnostic = ($output | Out-String) }
    }
    $fields = ([string]$output[-1]).Trim() -split '\s+'
    $freePercent = if ($fields.Count -ge 6 -and [double]$fields[1] -gt 0) {
        [math]::Round(100 * [double]$fields[3] / [double]$fields[1], 2)
    } else { 0 }
    [pscustomobject]@{
        status = if ($freePercent -ge $MinimumFreePercent) { "pass" } else { "insufficient_headroom" }
        volume = $Name
        linux_free_percent = $freePercent
    }
}

function Get-StorageChecks($Configuration) {
    foreach ($service in $Configuration.services.PSObject.Properties) {
        foreach ($mount in $service.Value.volumes) {
            if ($mount.type -eq "volume") {
                $name = $Configuration.volumes.($mount.source).name
                $access = Test-LinuxVolume $name $service.Value.image
                $drive = Get-DockerBackingDrive
            } elseif ($mount.type -eq "bind") {
                $name = $mount.source
                $access = if (Test-Path -LiteralPath $name -PathType Container) {
                    Test-DirectoryAccess $name
                } else { [pscustomobject]@{ status = "directory_missing" } }
                $drive = Get-DriveReport $name
            } else {
                $access = [pscustomobject]@{ status = "unsupported_mount" }
                $drive = [pscustomobject]@{ status = "not_observed" }
                $name = $mount.source
            }
            if ($access.status -ne "pass") { $failures.Add("$($service.Name)/$($mount.target): $($access.status)") }
            if ($drive.status -ne "pass") { $failures.Add("$($service.Name)/$($mount.target): $($drive.status)") }
            [pscustomobject]@{
                service = $service.Name; type = $mount.type; source = $name
                target = $mount.target; access = $access; drive = $drive
            }
        }
    }
}
