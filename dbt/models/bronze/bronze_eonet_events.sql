{{ config(materialized='table') }}

select
  event_id,
  title,
  category,
  event_date,
  raw_json,
  ingested_at
from read_parquet('{{ var("data_dir") }}/bronze/eonet_events.parquet')
