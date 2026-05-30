import os
import json
import logging
from datetime import datetime
from pathlib import Path
import boto3
from botocore.exceptions import NoCredentialsError, ClientError
from dotenv import load_dotenv

# ==============================================================================
# Configure Production Logging
# ==============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("feedback_pipeline.ingestion")

# ==============================================================================
# 1. Environment Loading & Security
# ==============================================================================
# Resolve absolute path to the git-ignored .env file inside the project root
ROOT_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT_DIR / ".env"

if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)
    logger.info(f"Successfully loaded configuration variables from {ENV_PATH}")
else:
    logger.warning(f"No environment config found at {ENV_PATH}. Attempting local system variables.")

# Read S3 and AWS parameters from the environment
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
BUCKET_NAME = os.getenv("S3_RAW_BUCKET_NAME")

# ==============================================================================
# 2. Raw Synthetic Feedback Generator
# ==============================================================================
# We generate a diverse, messy list of feedback entries across multiple channels
# (reviews, support tickets, survey responses) with varying sentiments to
# evaluate and train our Snowflake Cortex AI sentiment analysis model.
SYNTHETIC_FEEDBACK = [
    {
        "feedback_id": "FB-2026-0001",
        "customer_id": "CUST-9901",
        "customer_name": "Marcus Aurelius",
        "product_name": "Premium Leather Journal",
        "channel": "Website Review",
        "rating": 5,
        "feedback_text": "I absolutely love this journal! The leather smell is genuine, the binding is sturdy, and the paper is thick enough for my fountain pen without bleeding. Best purchase I have made this year. High quality, highly recommended!",
        "submitted_at": "2026-05-30T10:15:00Z"
    },
    {
        "feedback_id": "FB-2026-0002",
        "customer_id": "CUST-9902",
        "customer_name": "Janice Hopkins",
        "product_name": "Wireless Noise-Cancelling Headphones",
        "channel": "Support Ticket",
        "rating": 1,
        "feedback_text": "Extremely disappointed. The bluetooth connection cuts out constantly, and the active noise cancellation has an annoying static hiss. I tried reaching out to support but sat on hold for 40 minutes only to be disconnected. I want my money back immediately.",
        "submitted_at": "2026-05-30T11:45:30Z"
    },
    {
        "feedback_id": "FB-2026-0003",
        "customer_id": "CUST-9903",
        "customer_name": "David Miller",
        "product_name": "Ergonomic Office Chair",
        "channel": "Post-Purchase Survey",
        "rating": 3,
        "feedback_text": "The chair is decent and provides average lumbar support. Assembly was moderately frustrating because two screws were missing from the package. It does the job but is overpriced for what you get.",
        "submitted_at": "2026-05-30T12:00:15Z"
    },
    {
        "feedback_id": "FB-2026-0004",
        "customer_id": "CUST-9904",
        "customer_name": "Elena Rostova",
        "product_name": "Smart Fitness Tracker v2",
        "channel": "App Store Review",
        "rating": 5,
        "feedback_text": "Remarkable battery life! Lasts for 10 days on a single charge. The sleep tracking metrics are incredibly detailed and accurate. The companion app UI is smooth and syncs seamlessly. Brilliant!",
        "submitted_at": "2026-05-30T14:20:00Z"
    },
    {
        "feedback_id": "FB-2026-0005",
        "customer_id": "CUST-9905",
        "customer_name": "Samuel Vance",
        "product_name": "Premium Leather Journal",
        "channel": "Website Review",
        "rating": 2,
        "feedback_text": "The design looks okay but the shipping took three weeks to arrive, and when it did, the corners of the front cover were bent. The paper quality is fair, but customer support never answered my refund queries.",
        "submitted_at": "2026-05-30T16:10:45Z"
    }
]

# ==============================================================================
# 3. AWS S3 Upload Engine
# ==============================================================================
def verify_configuration() -> bool:
    """Validates that all essential AWS S3 environment variables are loaded."""
    missing_variables = []
    if not AWS_ACCESS_KEY or "YOUR_AWS_ACCESS" in AWS_ACCESS_KEY:
        missing_variables.append("AWS_ACCESS_KEY_ID")
    if not AWS_SECRET_KEY or "YOUR_AWS_SECRET" in AWS_SECRET_KEY:
        missing_variables.append("AWS_SECRET_ACCESS_KEY")
    if not BUCKET_NAME or "your-feedback-raw" in BUCKET_NAME:
        missing_variables.append("S3_RAW_BUCKET_NAME")
        
    if missing_variables:
        logger.error(
            f"\n==============================================================================\n"
            f"[AWS CONFIGURATION ERROR]\n"
            f"Required credentials missing from environment: {', '.join(missing_variables)}\n"
            f"Please ensure '{ENV_PATH}' has valid keys and S3 bucket details.\n"
            f"==============================================================================\n"
        )
        return False
    return True

def upload_feedback_to_s3(data: list) -> bool:
    """
    Standardizes the raw feedback payload as JSON, and streams it 
    directly to the partitioned folder inside your AWS S3 landing bucket.
    
    :param data: List of feedback dictionaries.
    :return: True if upload succeeded, False otherwise.
    """
    if not verify_configuration():
        return False
        
    # Standardize the partition name using current date
    partition_date = datetime.utcnow().strftime("%Y-%m-%d")
    s3_key = f"raw/feedback/{partition_date}.json"
    
    logger.info(f"Initializing AWS S3 Ingestion stream to bucket: {BUCKET_NAME}...")
    
    try:
        # Create S3 client connection using loaded credentials
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=AWS_ACCESS_KEY,
            aws_secret_access_key=AWS_SECRET_KEY,
            region_name=AWS_REGION
        )
        
        # Serialize list of dictionaries to string JSON payload
        json_payload = json.dumps(data, indent=2, default=str)
        
        # Push file stream natively
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=s3_key,
            Body=json_payload,
            ContentType="application/json"
        )
        
        logger.info(f"[INGESTION SUCCESS] Successfully wrote file stream to: s3://{BUCKET_NAME}/{s3_key}")
        return True
        
    except NoCredentialsError:
        logger.error("[INGESTION FAILED] AWS S3 authentication failed. Verify credentials inside your .env.")
        return False
    except ClientError as ce:
        logger.error(f"[INGESTION FAILED] S3 client returned error: {ce}")
        return False
    except Exception as e:
        logger.error(f"[INGESTION FAILED] An unexpected connection error occurred: {e}")
        return False

# ==============================================================================
# Main Orchestration Loop
# ==============================================================================
if __name__ == "__main__":
    logger.info("Executing Phase 3: Synthetic Feedback Ingestion Sequence...")
    success = upload_feedback_to_s3(SYNTHETIC_FEEDBACK)
    if success:
        logger.info("Phase 3 Execution sequence finished successfully.")
    else:
        logger.error("Phase 3 Execution sequence terminated with errors.")
