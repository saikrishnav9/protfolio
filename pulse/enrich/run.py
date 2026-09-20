from __future__ import annotations

import json
from typing import Any

from pulse.config import Settings, get_settings
from pulse.enrich.heuristic import heuristic_enrich
from pulse.enrich.llm import enrich_row, select_provider
from pulse.ingest.normalize import EVENT_COLUMNS, nearest_city_weather, normalize_eonet_event, normalize_nws_feature
from pulse.io_utils import read_json, write_json, write_parquet
from pulse.models import PipelineRun, iso

GOLD_COLUMNS = EVENT_COLUMNS + [
    "weather_city",
    "weather_distance_km",
    "temperature_c",
    "wind_speed_kmh",
    "precipitation_mm",
    "hazard_family",
    "severity_score",
    "impact_summary",
    "recommended_audience",
    "entities_json",
    "confidence",
    "enricher",
    "model",
    "prompt_version",
    "tokens_in",
    "tokens_out",
    "cost_usd",
    "enriched_at",
]


def load_normalized_events(settings: Settings) -> list[dict[str, Any]]:
    path = settings.bronze_dir / "normalized_events.json"
    if path.exists():
        return read_json(path)
    nws = read_json(settings.bronze_dir / "nws_alerts.raw.json")
    eonet = read_json(settings.bronze_dir / "eonet_events.raw.json")
    ingested_at = iso()
    rows = [normalize_nws_feature(f, ingested_at) for f in nws.get("features") or []]
    rows += [normalize_eonet_event(e, ingested_at) for e in eonet.get("events") or []]
    return rows


def load_weather(settings: Settings) -> list[dict[str, Any]]:
    path = settings.bronze_dir / "weather_snapshots.raw.json"
    if not path.exists():
        return []
    payload = read_json(path)
    if isinstance(payload, list):
        return payload
    return []


def enrich_events(settings: Settings | None = None, run: PipelineRun | None = None) -> list[dict[str, Any]]:
    settings = settings or get_settings()
    events = load_normalized_events(settings)
    weather = load_weather(settings)
    provider = select_provider(settings)
    cap = settings.pulse_max_enrich_rows
    llm_budget_rows = cap if provider else 0

    if run:
        if provider is None:
            run.llm_skipped_reason = "no_api_key"
            run.enricher = "heuristic"
        else:
            run.enricher = provider.name
            run.model = provider.model

    gold: list[dict[str, Any]] = []
    tokens_in = tokens_out = 0
    llm_used = False
    enriched_at = iso()

    for index, event in enumerate(events):
        wx = nearest_city_weather(event.get("latitude"), event.get("longitude"), weather) or {}
        merged = {**event, **wx}
        if provider and index < llm_budget_rows:
            extra = enrich_row(merged, provider)
            if extra.get("enricher") == "llm":
                llm_used = True
        else:
            extra = heuristic_enrich(merged)
            if provider and index >= llm_budget_rows and run and not run.llm_skipped_reason:
                run.llm_skipped_reason = f"row_cap_{cap}"
        tokens_in += int(extra.get("tokens_in") or 0)
        tokens_out += int(extra.get("tokens_out") or 0)
        row = {
            **event,
            "weather_city": wx.get("weather_city"),
            "weather_distance_km": wx.get("weather_distance_km"),
            "temperature_c": wx.get("temperature_c"),
            "wind_speed_kmh": wx.get("wind_speed_kmh"),
            "precipitation_mm": wx.get("precipitation_mm"),
            "hazard_family": extra["hazard_family"],
            "severity_score": extra["severity_score"],
            "impact_summary": extra["impact_summary"],
            "recommended_audience": extra["recommended_audience"],
            "entities_json": json.dumps(extra.get("entities") or []),
            "confidence": extra["confidence"],
            "enricher": extra["enricher"],
            "model": extra["model"],
            "prompt_version": extra["prompt_version"],
            "tokens_in": extra.get("tokens_in") or 0,
            "tokens_out": extra.get("tokens_out") or 0,
            "cost_usd": extra.get("cost_usd") or 0.0,
            "enriched_at": enriched_at,
        }
        gold.append(row)

    gold_path = settings.data_dir / "gold" / "gold_events.parquet"
    write_parquet(gold_path, gold, GOLD_COLUMNS)
    write_json(settings.data_dir / "gold" / "gold_events.json", gold)

    if run:
        run.gold_rows = len(gold)
        run.silver_rows = len(events)
        run.llm_called = llm_used
        run.tokens_in = tokens_in
        run.tokens_out = tokens_out
        run.cost_usd = 0.0
        if provider is None:
            run.llm_called = False
        elif not llm_used and run.llm_skipped_reason is None:
            run.llm_skipped_reason = "llm_failed_json_or_http"

    return gold
