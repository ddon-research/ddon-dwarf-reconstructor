$ErrorActionPreference = "Stop"

function Invoke-Checked([string]$Description, [scriptblock]$Command) {
    Write-Host "==> $Description"
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Description failed with exit code $LASTEXITCODE"
    }
}

Invoke-Checked "Ruff lint" { uvx ruff check --no-fix src tests }
Invoke-Checked "Ruff format" { uvx ruff format --check src tests }
Invoke-Checked "mypy" { uv run mypy src }
Invoke-Checked "Python structure budgets" { uv run python scripts/quality/check_structure.py }
Invoke-Checked "DDD and hexagonal boundaries" { uv run python scripts/quality/check_boundaries.py }
Invoke-Checked "Prospector diagnostics" { uv run prospector --profile .prospector.yml --tool pylint --tool pyflakes --tool mccabe src }
Invoke-Checked "unit tests" { uv run pytest -m unit }
