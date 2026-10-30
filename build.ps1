$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command py -ErrorAction SilentlyContinue }
if (-not $py) { $py = Get-Command python3 -ErrorAction SilentlyContinue }
if (-not $py) {
    Write-Host "python not found in PATH." -ForegroundColor Red
    Write-Host "  Install from https://python.org and re-open the terminal." -ForegroundColor Yellow
    exit 1
}

$pyArgs = @("build.py") + $args
& $py.Source @pyArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
