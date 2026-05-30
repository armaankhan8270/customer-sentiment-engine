import os
import logging
from typing import Dict, List, Any
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import snowflake.connector
from dotenv import load_dotenv

# ==============================================================================
# Configure Production Logging
# ==============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("feedback_pipeline.api")

# ==============================================================================
# 1. Environment Configurations
# ==============================================================================
ROOT_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT_DIR / ".env"

if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)
    logger.info(f"Loaded credentials inside API Server from {ENV_PATH}")
else:
    logger.warning(f"No environment config found at {ENV_PATH}. API will utilize system variables.")

# Verify credentials are ready
SF_ACCOUNT = os.getenv("SNOWFLAKE_ACCOUNT")
SF_USER = os.getenv("SNOWFLAKE_USER")
SF_PASSWORD = os.getenv("SNOWFLAKE_PASSWORD")
SF_ROLE = os.getenv("SNOWFLAKE_ROLE", "ACCOUNTADMIN")
SF_WAREHOUSE = os.getenv("SNOWFLAKE_WAREHOUSE", "test")
SF_DATABASE = os.getenv("SNOWFLAKE_DATABASE", "CUSTOMER_FEEDBACK_DB")
SF_SCHEMA = os.getenv("SNOWFLAKE_SCHEMA", "MART")  # Note: API queries from the Gold layer (MART schema)

# ==============================================================================
# 2. FastAPI Application Initialization
# ==============================================================================
app = FastAPI(
    title="Intelligent Customer Feedback & Sentiment Engine API",
    description="Asynchronous REST API serving Snowflake Cortex AI enriched consumer insights.",
    version="1.0.0"
)

# Enable CORS (Cross-Origin Resource Sharing)
# This allows our upcoming HTML/CSS frontend dashboard to query this API
# even if it is hosted on a different port or local domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permits all origins in development; tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==============================================================================
# 3. Snowflake Connection Helper
# ==============================================================================
def execute_snowflake_query(sql_query: str) -> List[Dict[str, Any]]:
    """
    Connects to Snowflake, executes a SQL query against the Gold marts, 
    fetches all rows, maps them to dictionaries, and closes the connection.
    
    :param sql_query: Standard SQL string query.
    :return: List of dictionaries matching database rows.
    """
    if not SF_ACCOUNT or not SF_USER or not SF_PASSWORD:
        logger.error("[DATABASE ERROR] Database credentials are missing from .env!")
        raise HTTPException(
            status_code=500, 
            detail="Database connection settings are unconfigured on the server."
        )

    conn = None
    try:
        # Establish connection using connector
        conn = snowflake.connector.connect(
            account=SF_ACCOUNT,
            user=SF_USER,
            password=SF_PASSWORD,
            role=SF_ROLE,
            warehouse=SF_WAREHOUSE,
            database=SF_DATABASE,
            schema=SF_SCHEMA
        )
        
        cursor = conn.cursor(snowflake.connector.DictCursor)
        logger.info(f"Executing query against Gold Marts: {sql_query}")
        cursor.execute(sql_query)
        rows = cursor.fetchall()
        
        # Standardize lowercase column keys and universally cast Decimals to floats
        import decimal
        standardized_rows = []
        for row in rows:
            clean_row = {}
            for k, v in row.items():
                if isinstance(v, decimal.Decimal):
                    v = float(v)
                clean_row[k.lower()] = v
            standardized_rows.append(clean_row)
            
        return standardized_rows

    except snowflake.connector.errors.DatabaseError as de:
        logger.error(f"[DATABASE EXCEPTION] Failed database operation: {de}")
        raise HTTPException(status_code=500, detail=f"Database execution failed: {de}")
    except Exception as e:
        logger.error(f"[DATABASE UNEXPECTED EXCEPTION] unexpected connector exception: {e}")
        raise HTTPException(status_code=500, detail="Unexpected database connection error.")
    finally:
        if conn:
            conn.close()
            logger.info("Closed database connection pool.")

# ==============================================================================
# 4. API Endpoint Definitions
# ==============================================================================

@app.get("/")
def get_root() -> Dict[str, str]:
    """Base root endpoint returning API metadata status."""
    return {
        "status": "online",
        "engine": "Intelligent Customer Feedback & Sentiment Engine API",
        "documentation": "/docs"  # FastAPI autogenerates interactive Swagger documentation here
    }

@app.get("/api/feedback")
def get_all_feedback() -> List[Dict[str, Any]]:
    """
    Retrieves all records from the Gold analytical fact table fct_customer_feedback,
    including raw reviews, rating scores, AI Cortex sentiment scores, and AI summaries.
    """
    query = """
        SELECT 
            feedback_id,
            customer_id,
            customer_name,
            product_name,
            channel,
            rating,
            feedback_text,
            submitted_at,
            sentiment_score,
            review_summary
        FROM CUSTOMER_FEEDBACK_DB.MART.FCT_CUSTOMER_FEEDBACK
        ORDER BY submitted_at DESC;
    """
    records = execute_snowflake_query(query)
    return records

@app.get("/api/metrics")
def get_feedback_metrics() -> Dict[str, Any]:
    """
    Queries the Gold analytics layer to calculate aggregate dashboard metrics in real-time,
    such as average ratings, overall sentiment score, review volume, and positive sentiment ratio.
    """
    query = """
        SELECT 
            COUNT(feedback_id) as total_reviews,
            ROUND(AVG(rating), 2) as average_rating,
            ROUND(AVG(sentiment_score), 4) as average_sentiment,
            COUNT(CASE WHEN sentiment_score >= 0.25 THEN 1 END) as positive_reviews_count
        FROM CUSTOMER_FEEDBACK_DB.MART.FCT_CUSTOMER_FEEDBACK;
    """
    rows = execute_snowflake_query(query)
    if not rows or rows[0].get("total_reviews", 0) == 0:
        return {
            "total_reviews": 0,
            "average_rating": 0.0,
            "average_sentiment": 0.0,
            "positive_ratio": 0.0
        }
        
    metrics = rows[0]
    total = metrics.get("total_reviews", 0)
    positives = metrics.get("positive_reviews_count", 0)
    
    # Calculate ratio of positive reviews
    ratio = round((positives / total) * 100, 2) if total > 0 else 0.0
    
    return {
        "total_reviews": total,
        "average_rating": metrics.get("average_rating", 0.0),
        "average_sentiment": metrics.get("average_sentiment", 0.0),
        "positive_ratio": ratio
    }

@app.get("/api/alerts")
def get_negative_alerts() -> List[Dict[str, Any]]:
    """
    Filters the Gold analytical layer for extremely negative feedback records
    where the AI sentiment score is strictly below -0.5, enabling operations
    to immediately identify and resolve customer complaints.
    """
    query = """
        SELECT 
            feedback_id,
            customer_name,
            product_name,
            channel,
            rating,
            feedback_text,
            sentiment_score,
            review_summary
        FROM CUSTOMER_FEEDBACK_DB.MART.FCT_CUSTOMER_FEEDBACK
        WHERE sentiment_score <= -0.5
        ORDER BY sentiment_score ASC;
    """
    alerts = execute_snowflake_query(query)
    return alerts
