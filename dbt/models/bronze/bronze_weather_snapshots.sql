{{ config(materialized='table') }}

select
  city,
  latitude,
  longitude,
  observed_at,
  temperature_c,
  wind_speed_kmh,
  precipitation_mm,
  weather_code
from read_parquet('{{ var("data_dir") }}/bronze/weather_snapshots.parquet')
