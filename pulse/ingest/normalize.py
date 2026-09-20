from __future__ import annotations

import math
import re
from typing import Any

from pulse.io_utils import payload_hash

STATE_FROM_UGC = re.compile(r"\b([A-Z]{2})[CZ]\d{3}\b")


def _centroid(geometry: dict[str, Any] | None) -> tuple[float | None, float | None]:
    if not geometry:
        return None, None
    gtype = geometry.get("type")
    coords = geometry.get("coordinates")
    if not coords:
        return None, None
    if gtype == "Point" and len(coords) >= 2:
        return float(coords[1]), float(coords[0])
    points: list[tuple[float, float]] = []

    def walk(node: Any) -> None:
        if isinstance(node, (list, tuple)) and node and isinstance(node[0], (int, float)):
            if len(node) >= 2:
                points.append((float(node[1]), float(node[0])))
            return
        if isinstance(node, (list, tuple)):
            for child in node:
                walk(child)

    walk(coords)
    if not points:
        return None, None
    lat = sum(p[0] for p in points) / len(points)
    lon = sum(p[1] for p in points) / len(points)
    return lat, lon


def _state_from_nws(props: dict[str, Any]) -> str | None:
    geocode = props.get("geocode") or {}
    for code in geocode.get("UGC") or []:
        match = STATE_FROM_UGC.search(str(code))
        if match:
            return match.group(1)
    same = geocode.get("SAME") or []
    if same:
        # SAME is 6-digit; first 2 after FIPS state often in areaDesc.
        pass
    area = props.get("areaDesc") or ""
    match = re.search(r",\s*([A-Z]{2})\b", area)
    if match:
        return match.group(1)
    return None


NWS_SEVERITY_RANK = {
    "extreme": 5,
    "severe": 4,
    "moderate": 3,
    "minor": 2,
    "unknown": 1,
}


def normalize_nws_feature(feature: dict[str, Any], ingested_at: str) -> dict[str, Any]:
    props = feature.get("properties") or {}
    lat, lon = _centroid(feature.get("geometry"))
    event_name = props.get("event") or props.get("headline") or "Unknown NWS event"
    source_id = str(props.get("id") or feature.get("id") or payload_hash(feature))
    severity = (props.get("severity") or "Unknown").title()
    return {
        "event_id": f"nws:{source_id}",
        "source": "nws",
        "source_event_id": source_id,
        "event_name": str(event_name),
        "category": props.get("category") or "Met",
        "severity_raw": severity,
        "severity_rank": NWS_SEVERITY_RANK.get(severity.lower(), 1),
        "certainty": props.get("certainty"),
        "urgency": props.get("urgency"),
        "headline": props.get("headline") or event_name,
        "description": (props.get("description") or "")[:4000],
        "instruction": (props.get("instruction") or "")[:2000],
        "area_desc": props.get("areaDesc"),
        "latitude": lat,
        "longitude": lon,
        "state_or_region": _state_from_nws(props),
        "started_at": props.get("onset") or props.get("effective") or props.get("sent"),
        "ends_at": props.get("ends") or props.get("expires"),
        "ingested_at": ingested_at,
        "payload_hash": payload_hash(feature),
    }


def normalize_eonet_event(event: dict[str, Any], ingested_at: str) -> dict[str, Any]:
    categories = event.get("categories") or []
    category = categories[0]["title"] if categories else "Unknown"
    geometry = event.get("geometry") or []
    latest = geometry[-1] if geometry else {}
    coords = latest.get("coordinates") or [None, None]
    lon, lat = (None, None)
    if isinstance(coords, list) and len(coords) >= 2 and coords[0] is not None:
        lon, lat = float(coords[0]), float(coords[1])
    source_id = str(event.get("id") or payload_hash(event))
    title = event.get("title") or "EONET event"
    return {
        "event_id": f"eonet:{source_id}",
        "source": "eonet",
        "source_event_id": source_id,
        "event_name": title,
        "category": category,
        "severity_raw": "Unknown",
        "severity_rank": 3,
        "certainty": None,
        "urgency": None,
        "headline": title,
        "description": (event.get("description") or title)[:4000],
        "instruction": None,
        "area_desc": None,
        "latitude": lat,
        "longitude": lon,
        "state_or_region": None,
        "started_at": latest.get("date"),
        "ends_at": None,
        "ingested_at": ingested_at,
        "payload_hash": payload_hash(event),
    }


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def nearest_city_weather(
    lat: float | None,
    lon: float | None,
    weather_rows: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if lat is None or lon is None or not weather_rows:
        return None
    best = None
    best_km = 10**9
    for row in weather_rows:
        km = haversine_km(lat, lon, float(row["latitude"]), float(row["longitude"]))
        if km < best_km:
            best_km = km
            best = row
    if best is None or best_km > 1200:
        return None
    return {
        "weather_city": best["city"],
        "weather_distance_km": round(best_km, 1),
        "temperature_c": best.get("temperature_c"),
        "wind_speed_kmh": best.get("wind_speed_kmh"),
        "precipitation_mm": best.get("precipitation_mm"),
    }


EVENT_COLUMNS = [
    "event_id",
    "source",
    "source_event_id",
    "event_name",
    "category",
    "severity_raw",
    "severity_rank",
    "certainty",
    "urgency",
    "headline",
    "description",
    "instruction",
    "area_desc",
    "latitude",
    "longitude",
    "state_or_region",
    "started_at",
    "ends_at",
    "ingested_at",
    "payload_hash",
]

WEATHER_COLUMNS = [
    "city",
    "latitude",
    "longitude",
    "observed_at",
    "temperature_c",
    "wind_speed_kmh",
    "precipitation_mm",
    "weather_code",
]

BRONZE_NWS_COLUMNS = ["alert_id", "sent", "event", "severity", "area_desc", "raw_json", "ingested_at"]
BRONZE_EONET_COLUMNS = ["event_id", "title", "category", "event_date", "raw_json", "ingested_at"]
