@echo off
REM ==============================================================================
REM Pipeline Runner & Automation Script for Windows CMD
REM Imports .env values, runs Python S3 loaders, and launches the FastAPI server.
REM ==============================================================================

setlocal enabledelayedexpansion

echo [PIPELINE] Booting Customer Sentiment Engine Automation Pipeline...

if not exist ".env" (
    echo [PIPELINE ERROR] .env file was not found! Please copy .env.template to .env and fill in credentials.
    pause
    exit /b 1
)

REM Walk .env file line by line and load environment variables
for /f "usebackq delims=" %%x in (".env") do (
    set "line=%%x"
    REM Skip comments
    if not "!line:~0,1!"=="#" (
        for /f "tokens=1,2 delims=" %%a in ("%%x") do (
            set "var=%%a"
            for /f "tokens=1* delims=" %%i in ("!var!") do set "%%i"
        )
    )
)

echo [PIPELINE] Verifying Python library dependencies...
pip install -r requirements.txt
if %ERRORLEVEL% neq 0 (
    echo [PIPELINE ERROR] Failed to satisfy python dependencies.
    pause
    exit /b %ERRORLEVEL%
)

pip install fastapi uvicorn

echo [PIPELINE] Running Ingestion Script (Python -^> S3 Raw Landing Bucket)...
python scripts/ingest_feedback.py
if %ERRORLEVEL% neq 0 (
    echo [PIPELINE ERROR] Ingestion script execution failed.
    pause
    exit /b %ERRORLEVEL%
)

echo [PIPELINE SUCCESS] Ingestion complete. Launching FastAPI API Server...
echo [PIPELINE] Navigate to http://127.0.0.1:8000/docs for Swagger Interactive Docs
echo [PIPELINE] Open customer-sentiment-engine\frontend\index.html in your browser!

uvicorn scripts.api_server:app --host 127.0.0.1 --port 8000 --reload
if %ERRORLEVEL% neq 0 (
    echo [PIPELINE ERROR] FastAPI server terminated with errors.
    pause
    exit /b %ERRORLEVEL%
)
