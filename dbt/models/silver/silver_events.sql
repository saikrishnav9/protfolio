{{ config(materialized='table') }}

select
  event_id,
  source,
  source_event_id,
  event_name,
  category,
  severity_raw,
  severity_rank,
  certainty,
  urgency,
  headline,
  description,
  instruction,
  area_desc,
  latitude,
  longitude,
  state_or_region,
  started_at,
  ends_at,
  ingested_at,
  payload_hash
from read_json_auto('{{ var("data_dir") }}/bronze/normalized_events.json', format = 'array')
where event_id is not null
  and event_name is not null
  and source in ('nws', 'eonet')
qualify row_number() over (partition by event_id order by ingested_at desc) = 1
