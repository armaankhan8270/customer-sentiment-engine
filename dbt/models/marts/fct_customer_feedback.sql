with staging_source as (
    select * from {{ ref('stg_customer_feedback') }}
),

enriched_feedback as (
    select
        feedback_id,
        customer_id,
        customer_name,
        product_name,
        channel,
        rating,
        feedback_text,
        submitted_at,
        
        -- Fallback Sentiment calculation for Snowflake Trial Accounts
        -- Maps: 5 stars -> 1.0, 4 stars -> 0.5, 3 stars -> 0.0, 2 stars -> -0.5, 1 star -> -1.0
        ((rating - 3) / 2.0)::number(4, 2) as sentiment_score,
        
        -- Fallback Review Abstract: Truncates long review paragraphs dynamically
        case 
            when length(feedback_text) > 120 then substring(feedback_text, 1, 117) || '...'
            else feedback_text
        end as review_summary,
        
        raw_ingested_at
    from staging_source
)

select * from enriched_feedback
