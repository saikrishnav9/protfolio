from __future__ import annotations

import os
import shutil
import subprocess
import sys

from pathlib import Path

from pulse.config import Settings, get_settings
from pulse.io_utils import connect


class QualityGateError(Exception):
    def __init__(self, failures: list[str]):
        super().__init__("; ".join(failures))
        self.failures = failures


def _dbt_env(settings: Settings) -> dict[str, str]:
    env = os.environ.copy()
    data_dir = settings.data_dir.resolve()
    env["PULSE_DATA_DIR"] = data_dir.as_posix()
    env["PULSE_DUCKDB"] = (data_dir / "pulse.duckdb").as_posix()
    env["DBT_PROFILES_DIR"] = str(settings.dbt_dir)
    return env


def _dbt_bin() -> list[str]:
    scripts = Path(sys.executable).resolve().parent
    for name in ("dbt.exe", "dbt"):
        candidate = scripts / name
        if candidate.exists():
            return [str(candidate)]
    found = shutil.which("dbt")
    if found:
        return [found]
    return [sys.executable, "-m", "dbt.cli.main"]


def run_dbt(settings: Settings, args: list[str]) -> subprocess.CompletedProcess[str]:
    cmd = [*_dbt_bin(), *args, "--project-dir", str(settings.dbt_dir)]
    return subprocess.run(
        cmd,
        cwd=settings.dbt_dir,
        env=_dbt_env(settings),
        text=True,
        capture_output=True,
        check=False,
    )


def python_quality_checks(settings: Settings) -> list[str]:
    """Contract checks that must pass before any LLM call."""
    failures: list[str] = []
    bronze = settings.bronze_dir
    con = connect()

    nws = bronze / "nws_alerts.parquet"
    eonet = bronze / "eonet_events.parquet"
    if not nws.exists() or not eonet.exists():
        return ["bronze parquet missing"]

    null_events = con.execute(
        f"select count(*) from read_parquet('{nws.as_posix()}') where event is null or alert_id is null"
    ).fetchone()[0]
    if null_events:
        failures.append(f"bronze_nws_alerts: {null_events} rows missing event/alert_id")

    null_eonet = con.execute(
        f"select count(*) from read_parquet('{eonet.as_posix()}') where event_id is null or title is null"
    ).fetchone()[0]
    if null_eonet:
        failures.append(f"bronze_eonet_events: {null_eonet} rows missing event_id/title")

    normalized = bronze / "normalized_events.json"
    if not normalized.exists():
        failures.append("normalized_events.json missing")
        return failures

    dupes = con.execute(
        f"""
        select count(*) from (
          select event_id from read_json_auto('{normalized.as_posix()}', format='array')
          group by 1 having count(*) > 1
        )
        """
    ).fetchone()[0]
    if dupes:
        failures.append(f"silver_events: {dupes} duplicate event_id values")

    bad_source = con.execute(
        f"""
        select count(*) from read_json_auto('{normalized.as_posix()}', format='array')
        where source not in ('nws', 'eonet') or event_id is null or event_name is null
        """
    ).fetchone()[0]
    if bad_source:
        failures.append(f"silver_events: {bad_source} rows fail source/id/name contracts")

    return failures


def run_quality_gate(settings: Settings | None = None, use_dbt: bool = True) -> list[str]:
    settings = settings or get_settings()
    failures = python_quality_checks(settings)
    if failures:
        raise QualityGateError(failures)

    if not use_dbt:
        return []

    vars_flag = f"{{data_dir: '{settings.data_dir.as_posix()}'}}"
    run = run_dbt(settings, ["run", "--select", "bronze silver", "--vars", vars_flag])
    if run.returncode != 0:
        raise QualityGateError([f"dbt run failed: {run.stdout[-2000:]}\n{run.stderr[-2000:]}"])

    test = run_dbt(settings, ["test", "--select", "bronze silver", "--vars", vars_flag])
    if test.returncode != 0:
        raise QualityGateError([f"dbt test failed: {test.stdout[-2000:]}\n{test.stderr[-2000:]}"])
    return []


def run_gold_models(settings: Settings) -> None:
    vars_flag = f"{{data_dir: '{settings.data_dir.as_posix()}'}}"
    result = run_dbt(settings, ["run", "--select", "gold", "--vars", vars_flag])
    if result.returncode != 0:
        raise QualityGateError([f"dbt gold run failed: {result.stdout[-2000:]}\n{result.stderr[-2000:]}"])
