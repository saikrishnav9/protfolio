{{ config(materialized='table') }}

select
  hazard_family,
  recommended_audience,
  count(*) as event_count,
  avg(severity_score) as avg_severity,
  avg(confidence) as avg_confidence,
  sum(case when enricher = 'llm' then 1 else 0 end) as llm_rows,
  sum(case when enricher like 'heuristic%' then 1 else 0 end) as heuristic_rows
from {{ ref('gold_events') }}
group by 1, 2
order by event_count desc
