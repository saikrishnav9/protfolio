from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pulse.config import Settings, get_settings
from pulse.ingest.clients import fetch_eonet_events, fetch_nws_alerts, fetch_weather_snapshots
from pulse.ingest.normalize import (
    BRONZE_EONET_COLUMNS,
    BRONZE_NWS_COLUMNS,
    WEATHER_COLUMNS,
    normalize_eonet_event,
    normalize_nws_feature,
)
from pulse.io_utils import read_json, write_json, write_parquet
from pulse.models import PipelineRun, iso


def _load_fixture(settings: Settings, name: str) -> Any:
    return read_json(settings.fixtures_dir / name)


def ingest_bronze(settings: Settings | None = None, run: PipelineRun | None = None) -> dict[str, int]:
    settings = settings or get_settings()
    settings.bronze_dir.mkdir(parents=True, exist_ok=True)
    ingested_at = iso()
    warnings: list[str] = []

    nws_payload: dict[str, Any]
    eonet_payload: dict[str, Any]
    weather_rows: list[dict[str, Any]]

    if settings.pulse_offline:
        nws_payload = _load_fixture(settings, "nws_alerts.json")
        eonet_payload = _load_fixture(settings, "eonet_events.json")
        weather_rows = _load_fixture(settings, "weather_snapshots.json")
        if run:
            run.mode = "offline"
    else:
        try:
            nws_payload = fetch_nws_alerts(settings)
            eonet_payload = fetch_eonet_events(settings)
            weather_rows = fetch_weather_snapshots(settings)
        except Exception as exc:  # noqa: BLE001 — fallback keeps the demo alive
            warnings.append(f"live ingest failed ({exc}); using fixtures")
            nws_payload = _load_fixture(settings, "nws_alerts.json")
            eonet_payload = _load_fixture(settings, "eonet_events.json")
            weather_rows = _load_fixture(settings, "weather_snapshots.json")
            if run:
                run.mode = "fixture_fallback"

    write_json(settings.bronze_dir / "nws_alerts.raw.json", nws_payload)
    write_json(settings.bronze_dir / "eonet_events.raw.json", eonet_payload)
    write_json(settings.bronze_dir / "weather_snapshots.raw.json", weather_rows)

    nws_rows = []
    for feature in nws_payload.get("features") or []:
        props = feature.get("properties") or {}
        nws_rows.append(
            {
                "alert_id": str(props.get("id") or feature.get("id")),
                "sent": props.get("sent"),
                "event": props.get("event"),
                "severity": props.get("severity"),
                "area_desc": props.get("areaDesc"),
                "raw_json": json.dumps(feature, default=str),
                "ingested_at": ingested_at,
            }
        )

    eonet_rows = []
    for event in eonet_payload.get("events") or []:
        cats = event.get("categories") or []
        geometry = event.get("geometry") or []
        eonet_rows.append(
            {
                "event_id": str(event.get("id")),
                "title": event.get("title"),
                "category": cats[0]["title"] if cats else None,
                "event_date": geometry[-1].get("date") if geometry else None,
                "raw_json": json.dumps(event, default=str),
                "ingested_at": ingested_at,
            }
        )

    weather_out = [
        {k: row.get(k) for k in WEATHER_COLUMNS}
        for row in weather_rows
    ]

    nws_count = write_parquet(settings.bronze_dir / "nws_alerts.parquet", nws_rows, BRONZE_NWS_COLUMNS)
    eonet_count = write_parquet(
        settings.bronze_dir / "eonet_events.parquet", eonet_rows, BRONZE_EONET_COLUMNS
    )
    weather_count = write_parquet(
        settings.bronze_dir / "weather_snapshots.parquet", weather_out, WEATHER_COLUMNS
    )

    # Silver-shaped normalized extract used by dbt and enrich.
    silver_like = [normalize_nws_feature(f, ingested_at) for f in nws_payload.get("features") or []]
    silver_like += [normalize_eonet_event(e, ingested_at) for e in eonet_payload.get("events") or []]
    write_json(settings.bronze_dir / "normalized_events.json", silver_like)

    if run:
        run.bronze_nws_rows = nws_count
        run.bronze_eonet_rows = eonet_count
        run.bronze_weather_rows = weather_count
        run.warnings.extend(warnings)

    return {
        "nws": nws_count,
        "eonet": eonet_count,
        "weather": weather_count,
        "normalized": len(silver_like),
    }


def bronze_paths(settings: Settings | None = None) -> dict[str, Path]:
    settings = settings or get_settings()
    return {
        "nws": settings.bronze_dir / "nws_alerts.parquet",
        "eonet": settings.bronze_dir / "eonet_events.parquet",
        "weather": settings.bronze_dir / "weather_snapshots.parquet",
    }
