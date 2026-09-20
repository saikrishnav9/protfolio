from __future__ import annotations

import os
from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

from pulse.config import ROOT, Settings, get_settings
from pulse.enrich.run import GOLD_COLUMNS, enrich_events
from pulse.ingest.run import ingest_bronze
from pulse.io_utils import connect, read_json, write_json, write_parquet
from pulse.models import PipelineRun, iso
from pulse.site_build import assemble_site
from pulse.transform import QualityGateError, run_gold_models, run_quality_gate


def _git_sha() -> str | None:
    return os.environ.get("GITHUB_SHA")


def _jsonable(value):
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _fetch_dicts(con, sql: str) -> list[dict]:
    result = con.execute(sql)
    cols = [col[0] for col in result.description]
    out = []
    for row in result.fetchall():
        out.append({cols[i]: _jsonable(row[i]) for i in range(len(cols))})
    return out


def _git_sha() -> str | None:
    return os.environ.get("GITHUB_SHA")


def export_dashboard(settings: Settings, run: PipelineRun) -> None:
    dest = settings.dashboard_data_dir
    dest.mkdir(parents=True, exist_ok=True)
    gold_src = settings.data_dir / "gold" / "gold_events.parquet"
    gold_json = settings.data_dir / "gold" / "gold_events.json"

    con = connect()
    if gold_src.exists():
        dest_gold = dest / "gold_events.parquet"
        dest_gold.write_bytes(gold_src.read_bytes())
        con.execute(
            f"""
            COPY (
              select
                cast(date_trunc('day', try_cast(started_at as timestamp)) as date) as event_day,
                source,
                count(*) as event_count,
                sum(case when severity_score >= 4 then 1 else 0 end) as high_severity_count,
                avg(confidence) as avg_confidence,
                sum(tokens_in) as tokens_in,
                sum(tokens_out) as tokens_out
              from read_parquet('{gold_src.as_posix()}')
              group by 1, 2
            ) TO '{(dest / "gold_daily.parquet").as_posix()}' (FORMAT PARQUET)
            """
        )
        con.execute(
            f"""
            COPY (
              select
                hazard_family,
                recommended_audience,
                count(*) as event_count,
                avg(severity_score) as avg_severity,
                avg(confidence) as avg_confidence,
                sum(case when enricher = 'llm' then 1 else 0 end) as llm_rows,
                sum(case when enricher like 'heuristic%' then 1 else 0 end) as heuristic_rows
              from read_parquet('{gold_src.as_posix()}')
              group by 1, 2
              order by event_count desc
            ) TO '{(dest / "gold_by_hazard.parquet").as_posix()}' (FORMAT PARQUET)
            """
        )
    else:
        write_parquet(dest / "gold_events.parquet", [], GOLD_COLUMNS)

    write_json(dest / "run_log.json", run.to_public_dict())
    if gold_json.exists():
        (dest / "gold_events.json").write_bytes(gold_json.read_bytes())

    if gold_src.exists():
        con.execute(
            f"CREATE OR REPLACE TABLE gold_events AS SELECT * FROM read_parquet('{gold_src.as_posix()}')"
        )
        canned_path = ROOT / "dashboard" / "canned_queries.json"
        if canned_path.exists():
            queries = read_json(canned_path)
            packaged = []
            for spec in queries:
                packaged.append(
                    {
                        "id": spec["id"],
                        "label": spec["label"],
                        "sql": spec["sql"],
                        "rows": _fetch_dicts(con, spec["sql"]),
                    }
                )
            write_json(dest / "query_results.json", packaged)

    assemble_site()


def run_pipeline(offline: bool | None = None, use_dbt: bool = True) -> PipelineRun:
    settings = get_settings()
    if offline is True:
        settings.pulse_offline = True
    elif offline is False:
        settings.pulse_offline = False

    run = PipelineRun(
        run_id=str(uuid4())[:8],
        started_at=iso(),
        git_sha=_git_sha(),
        mode="offline" if settings.pulse_offline else "live",
    )
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    os.environ["PULSE_DATA_DIR"] = settings.data_dir.as_posix()
    os.environ["PULSE_DUCKDB"] = (settings.data_dir / "pulse.duckdb").as_posix()

    ingest_bronze(settings, run)

    try:
        run_quality_gate(settings, use_dbt=use_dbt)
        run.tests_passed = True
    except QualityGateError as exc:
        run.tests_passed = False
        run.tests_failed = exc.failures
        run.status = "blocked_quality_gate"
        run.llm_skipped_reason = "quality_gate_failed"
        run.llm_called = False
        run.enricher = "skipped"
        run.finished_at = iso()
        export_dashboard(settings, run)
        write_json(settings.data_dir / "run_log.json", run.to_public_dict())
        return run

    enrich_events(settings, run)

    try:
        if use_dbt:
            run_gold_models(settings)
    except QualityGateError as exc:
        run.warnings.append(f"gold dbt models skipped/failed: {exc}")

    run.status = "success"
    run.finished_at = iso()
    export_dashboard(settings, run)
    write_json(settings.data_dir / "run_log.json", run.to_public_dict())
    return run
