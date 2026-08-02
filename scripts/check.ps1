$ErrorActionPreference = "Stop"

uv run just check
if ($LASTEXITCODE -ne 0) {
    throw "Tooling checks failed with exit code $LASTEXITCODE"
}

uv run just test-unit
if ($LASTEXITCODE -ne 0) {
    throw "Unit tests failed with exit code $LASTEXITCODE"
}
