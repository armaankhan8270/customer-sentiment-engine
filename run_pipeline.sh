#!/bin/bash
# ==============================================================================
# Pipeline Runner & Automation Script - Customer Sentiment Engine
# Loads environment variables, runs ingestion, and launches the FastAPI server.
# ==============================================================================

# 1. Resolve paths
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$PROJECT_ROOT/.env"

echo -e "\e[36m[PIPELINE] Booting Customer Sentiment Engine Automation Pipeline...\e[0m"

# 2. Load .env environment variables
if [ -f "$ENV_FILE" ]; then
    echo -e "\e[32m[PIPELINE] Loading credentials from $ENV_FILE...\e[0m"
    export $(grep -v '^#' "$ENV_FILE" | xargs)
else
    echo -e "\e[31m[PIPELINE ERROR] .env file was not found! Please create it inside the project root.\e[0m"
    exit 1
fi

# 3. Satisfy python dependencies
echo -e "\e[36m[PIPELINE] Verifying Python package dependencies...\e[0m"
pip install -r "$PROJECT_ROOT/requirements.txt"
pip install fastapi uvicorn

# 4. Phase 3: Python Ingestion (Upload to S3)
echo -e "\e[32m[PIPELINE] Running Ingestion Script (Python -> S3 Raw Landing Bucket)...\e[0m"
python "$PROJECT_ROOT/scripts/ingest_feedback.py"

if [ $? -ne 0 ]; then
    echo -e "\e[31m[PIPELINE ERROR] Python ingestion failed! Verify S3 credentials in your .env.\e[0m"
    exit 1
fi

# 5. Launch FastAPI server
echo -e "\e[32m[PIPELINE SUCCESS] Ingestion complete. Launching FastAPI API Server...\e[0m"
echo -e "\e[36m[PIPELINE] Navigate to http://127.0.0.1:8000/docs for Swagger Interactive Docs\e[0m"
echo -e "\e[36m[PIPELINE] Open customer-sentiment-engine/frontend/index.html in your browser!\e[0m"

cd "$PROJECT_ROOT"
uvicorn scripts.api_server:app --host 127.0.0.1 --port 8000 --reload
