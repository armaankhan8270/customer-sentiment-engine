-- ==============================================================================
-- Snowflake Infrastructure Setup - Customer Sentiment Engine
-- Run this complete script inside your Snowflake console worksheet.
-- ==============================================================================

-- 1. Create Analytics Database & Medallion Schemas
CREATE DATABASE IF NOT EXISTS CUSTOMER_FEEDBACK_DB;
USE DATABASE CUSTOMER_FEEDBACK_DB;

CREATE SCHEMA IF NOT EXISTS RAW;
CREATE SCHEMA IF NOT EXISTS STAGING;
CREATE SCHEMA IF NOT EXISTS MART;
CREATE SCHEMA IF NOT EXISTS SNAPSHOT;

USE SCHEMA RAW;

-- 2. Create file formats for schema-on-read ingestion
-- File format to parse semi-structured raw feedback JSON
CREATE OR REPLACE FILE FORMAT JSON_FORMAT
  TYPE = 'JSON'
  STRIP_OUTER_ARRAY = TRUE
  IGNORE_UTF8_ERRORS = TRUE;

-- File format to parse raw feedback CSV
CREATE OR REPLACE FILE FORMAT CSV_FORMAT
  TYPE = 'CSV'
  FIELD_DELIMITER = ','
  SKIP_HEADER = 1
  FIELD_OPTIONALLY_ENCLOSED_BY = '"'
  NULL_IF = ('', 'NULL')
  EMPTY_FIELD_AS_NULL = TRUE;

-- 3. Create raw staging area pointing securely to S3
-- Placed real IAM credentials and target bucket dynamically
CREATE OR REPLACE STAGE RAW_S3_STAGE
  URL = 's3://customer-feedback-raw-landing-bucket/'
  CREDENTIALS = (
    AWS_KEY_ID = '<YOUR_AWS_ACCESS_KEY_ID>' 
    AWS_SECRET_KEY = '<YOUR_AWS_SECRET_ACCESS_KEY>'
  )
  COMMENT = 'AWS S3 Stage connecting to Raw Feedback Ingestion Bucket';

-- 4. Establish Raw Landing Bronze Table (using Variant column)
-- This table stores nested feedback files exactly as they arrive from S3
CREATE OR REPLACE TABLE RAW.CUSTOMER_FEEDBACK_RAW (
  src_data VARIANT,
  ingested_at TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP()
) COMMENT = 'Bronze Raw Variant Landing for feedback records';
