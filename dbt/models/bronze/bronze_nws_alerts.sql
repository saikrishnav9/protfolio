{{ config(materialized='table') }}

select
  alert_id,
  sent,
  event,
  severity,
  area_desc,
  raw_json,
  ingested_at
from read_parquet('{{ var("data_dir") }}/bronze/nws_alerts.parquet')
