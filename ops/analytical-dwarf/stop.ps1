# Stop database processes gracefully before stopping their container wrappers.
[CmdletBinding()]
param([ValidateRange(1, 600)][int]$TimeoutSeconds = 120)
$ErrorActionPreference = "Stop"
$compose = @("compose", "--env-file", (Join-Path $PSScriptRoot ".env"),
    "-f", (Join-Path $PSScriptRoot "compose.yaml"),
    "-f", (Join-Path $PSScriptRoot "compose.storage-linux.yaml"))
foreach ($role in @("be", "fe")) {
    $service = "doris-$role"
    $id = & docker @compose ps --all --quiet $service
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($id)) { throw "Missing service: $service" }
    $running = & docker inspect --format '{{.State.Running}}' $id
    if ($running -eq "false") { continue }
    & docker @compose exec -T $service timeout $TimeoutSeconds bash "/opt/apache-doris/$role/bin/stop_$role.sh" --grace
    $stopExit = $LASTEXITCODE
    $running = & docker inspect --format '{{.State.Running}}' $id
    if ($stopExit -ne 0 -and $running -ne "false") {
        throw "Graceful $service shutdown failed ($stopExit); no forced stop was attempted"
    }
    # The application has exited; only an image's remaining wrapper may need a signal.
    & docker @compose stop --timeout 15 $service
    if ($LASTEXITCODE -ne 0) { throw "Container stop failed: $service" }
}
