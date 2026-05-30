import os
import logging
from pathlib import Path
import snowflake.connector
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("feedback_pipeline.load_raw")

# 1. Load configurations
ROOT_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT_DIR / ".env"

if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)
    logger.info(f"Loaded credentials from {ENV_PATH}")
else:
    logger.error(f".env file not found at {ENV_PATH}!")
    exit(1)

# 2. Establish Snowflake Connection
logger.info("Connecting to Snowflake database...")
try:
    conn = snowflake.connector.connect(
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        role=os.getenv("SNOWFLAKE_ROLE", "ACCOUNTADMIN"),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE", "test"),
        database=os.getenv("SNOWFLAKE_DATABASE", "CUSTOMER_FEEDBACK_DB"),
        schema="RAW"
    )
    cursor = conn.cursor()
    
    # 3. Execute COPY INTO Ingestion using SELECT $1 Transformation
    logger.info("Executing Copy-with-Transformation RAW.CUSTOMER_FEEDBACK_RAW from S3 Stage...")
    copy_query = """
    COPY INTO CUSTOMER_FEEDBACK_DB.RAW.CUSTOMER_FEEDBACK_RAW (src_data)
      FROM (
        SELECT $1 
        FROM @RAW_S3_STAGE/raw/feedback/
      )
      FILE_FORMAT = (TYPE = 'JSON' STRIP_OUTER_ARRAY = TRUE)
      PATTERN = '.*\\.json';
    """
    cursor.execute(copy_query)
    
    # Fetch execution summary status
    results = cursor.fetchall()
    if results:
        logger.info(f"[LOAD SUCCESS] File loaded: {results[0][0]}, Status: {results[0][1]}")
    else:
        logger.warning("[LOAD WARNING] No files were loaded. The file might already be copied or not found on S3.")
        
except Exception as e:
    logger.error(f"[LOAD FAILED] Failed to copy raw data: {e}")
finally:
    if 'conn' in locals() and conn:
        conn.close()
        logger.info("Closed Snowflake database connection.")
