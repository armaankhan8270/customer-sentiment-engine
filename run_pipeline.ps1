# ==============================================================================
# Pipeline Runner & Automation Script for Windows Powershell
# Imports .env values, runs Python S3 loaders, and launches the FastAPI server.
# ==============================================================================

# 1. Resolve paths
$ProjectRoot = $PSScriptRoot
$EnvFile = Join-Path $ProjectRoot ".env"

Write-Host "[PIPELINE] Booting Customer Sentiment Engine Automation Pipeline..." -ForegroundColor Cyan

# 2. Load .env environment variables into Process scope
if (Test-Path $EnvFile) {
    Write-Host "[PIPELINE] Loading credentials from $EnvFile..." -ForegroundColor Green
    Get-Content $EnvFile | Where-Object { $_ -match '=' -and $_ -notlike '#*' } | ForEach-Object {
        $parts = $_ -split '=', 2
        $key = $parts[0].Trim()
        $value = $parts[1].Trim()
        [System.Environment]::SetEnvironmentVariable($key, $value, "Process")
    }
} else {
    Write-Error "[PIPELINE ERROR] .env file was not found! Please create it by copying .env.template."
    exit 1
}

# 3. Satisfy python dependencies
Write-Host "[PIPELINE] Verifying Python library dependencies..." -ForegroundColor Cyan
pip install -r (Join-Path $ProjectRoot "requirements.txt")
pip install fastapi uvicorn

# 4. Ingestion layer (Python -> S3 Raw Ingest)
Write-Host "[PIPELINE] Running Ingestion Script (Python -> S3 Raw Landing Bucket)..." -ForegroundColor Green
python (Join-Path $ProjectRoot "scripts\ingest_feedback.py")

if ($LASTEXITCODE -ne 0) {
    Write-Error "[PIPELINE ERROR] Ingestion failed! Verify S3 credentials in your .env."
    exit 1
}

# 5. Launch FastAPI server
Write-Host "[PIPELINE SUCCESS] Ingestion complete. Launching FastAPI API Server..." -ForegroundColor Green
Write-Host "[PIPELINE] Navigate to http://127.0.0.1:8000/docs for Swagger Interactive Docs" -ForegroundColor Cyan
Write-Host "[PIPELINE] Open customer-sentiment-engine\frontend\index.html in your browser!" -ForegroundColor Cyan

Set-Location $ProjectRoot
uvicorn scripts.api_server:app --host 127.0.0.1 --port 8000 --reload
