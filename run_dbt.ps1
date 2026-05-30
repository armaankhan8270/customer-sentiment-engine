# ==============================================================================
# dbt Runner Automation Script for Windows Powershell
# Imports .env secrets and runs specified dbt commands.
# ==============================================================================

# 1. Resolve paths
$ProjectRoot = $PSScriptRoot
$EnvFile = Join-Path $ProjectRoot ".env"

# 2. Load .env environment variables into Process scope
if (Test-Path $EnvFile) {
    Get-Content $EnvFile | Where-Object { $_ -match '=' -and $_ -notlike '#*' } | ForEach-Object {
        $parts = $_ -split '=', 2
        $key = $parts[0].Trim()
        $value = $parts[1].Trim()
        [System.Environment]::SetEnvironmentVariable($key, $value, "Process")
    }
} else {
    Write-Error "[dbt RUNNER ERROR] .env file was not found!"
    exit 1
}

# 3. Enter dbt folder and run command
Set-Location (Join-Path $ProjectRoot "dbt")

if ($args.Count -eq 0) {
    Write-Host "[dbt RUNNER] No command specified. Defaulting to 'dbt run'..." -ForegroundColor Cyan
    dbt run --profiles-dir .
} else {
    Write-Host "[dbt RUNNER] Executing: dbt $args --profiles-dir ." -ForegroundColor Cyan
    dbt $args --profiles-dir .
}
