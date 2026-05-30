with raw_source as (
    select * from {{ source('raw', 'customer_feedback_raw') }}
),

staged_records as (
    select
        -- Extract keys from the semi-structured Variant column using path-indexing
        src_data:feedback_id::varchar as feedback_id,
        src_data:customer_id::varchar as customer_id,
        src_data:customer_name::varchar as customer_name,
        src_data:product_name::varchar as product_name,
        src_data:channel::varchar as channel,
        src_data:rating::int as rating,
        src_data:feedback_text::varchar as feedback_text,
        src_data:submitted_at::timestamp as submitted_at,
        ingested_at as raw_ingested_at
    from raw_source
)

select * from staged_records
