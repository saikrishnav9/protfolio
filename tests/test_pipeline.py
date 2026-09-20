from pulse.config import get_settings
from pulse.ingest.run import ingest_bronze
from pulse.io_utils import connect, write_parquet
from pulse.pipeline import run_pipeline
from pulse.transform import QualityGateError, python_quality_checks, run_quality_gate


def test_offline_pipeline_builds_gold():
    run = run_pipeline(offline=True, use_dbt=False)
    assert run.status == "success"
    assert run.tests_passed is True
    assert run.gold_rows >= 6
    assert run.cost_usd == 0.0
    assert run.llm_called is False
    settings = get_settings()
    gold = settings.dashboard_data_dir / "gold_events.parquet"
    assert gold.exists()
    queries = settings.dashboard_data_dir / "query_results.json"
    assert queries.exists()
    assembled = settings.data_dir.parent / "site" / "pulse" / "index.html"
    assert assembled.exists()
    con = connect()
    count = con.execute(f"select count(*) from read_parquet('{gold.as_posix()}')").fetchone()[0]
    assert count == run.gold_rows


def test_quality_gate_blocks_schema_drift():
    settings = get_settings()
    settings.pulse_offline = True
    ingest_bronze(settings)
    write_parquet(
        settings.bronze_dir / "nws_alerts.parquet",
        [{"alert_id": None, "sent": None, "event": None, "severity": None, "area_desc": None, "raw_json": "{}", "ingested_at": "x"}],
        ["alert_id", "sent", "event", "severity", "area_desc", "raw_json", "ingested_at"],
    )
    failures = python_quality_checks(settings)
    assert failures
    try:
        run_quality_gate(settings, use_dbt=False)
        raise AssertionError("expected quality gate to fail")
    except QualityGateError as exc:
        assert "event/alert_id" in str(exc)
