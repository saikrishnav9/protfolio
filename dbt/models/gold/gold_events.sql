{{ config(materialized='table') }}

select *
from read_parquet('{{ var("data_dir") }}/gold/gold_events.parquet')
