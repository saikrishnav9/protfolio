{{ config(materialized='table') }}

select
  cast(date_trunc('day', try_cast(started_at as timestamp)) as date) as event_day,
  source,
  count(*) as event_count,
  sum(case when severity_score >= 4 then 1 else 0 end) as high_severity_count,
  avg(confidence) as avg_confidence,
  sum(tokens_in) as tokens_in,
  sum(tokens_out) as tokens_out,
  sum(cost_usd) as cost_usd
from {{ ref('gold_events') }}
group by 1, 2
