from __future__ import annotations

import re
from typing import Any

HAZARD_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("tornado", ("tornado",)),
    ("severe_weather", ("thunderstorm", "severe weather", "wind", "hail", "storm")),
    ("flood", ("flood", "flash flood")),
    ("winter", ("winter", "blizzard", "ice storm", "snow", "freeze")),
    ("heat", ("heat", "excessive heat", "red flag")),
    ("wildfire", ("wildfire", "fire", "red flag")),
    ("volcano", ("volcano", "volcanic")),
    ("earthquake", ("earthquake", "seismic")),
    ("marine", ("marine", "rip current", "coastal", "tsunami")),
    ("air_quality", ("smoke", "dust", "air quality")),
]


AUDIENCE_BY_SEVERITY = {
    5: "emergency_ops",
    4: "emergency_ops",
    3: "public",
    2: "public",
    1: "analyst",
}


def _blob(row: dict[str, Any]) -> str:
    parts = [
        str(row.get("event_name") or ""),
        str(row.get("headline") or ""),
        str(row.get("category") or ""),
        str(row.get("description") or "")[:800],
        str(row.get("area_desc") or ""),
    ]
    return " ".join(parts).lower()


def classify_hazard(row: dict[str, Any]) -> str:
    text = _blob(row)
    for family, needles in HAZARD_RULES:
        if any(n in text for n in needles):
            return family
    source_cat = str(row.get("category") or "").lower()
    if "wildfire" in source_cat:
        return "wildfire"
    if "volcano" in source_cat:
        return "volcano"
    if "flood" in source_cat:
        return "flood"
    return "other"


def extract_entities(row: dict[str, Any]) -> list[str]:
    entities: list[str] = []
    if row.get("state_or_region"):
        entities.append(str(row["state_or_region"]))
    area = row.get("area_desc") or ""
    for token in re.split(r"[;]", area):
        token = token.strip()
        if token:
            entities.append(token.split(",")[0].strip()[:48])
    headline = str(row.get("headline") or "")
    for match in re.findall(r"\b[A-Z][a-z]+(?: [A-Z][a-z]+)?\b", headline):
        if match.lower() not in {"the", "and", "for", "until", "warning", "watch", "advisory"}:
            entities.append(match)
    # de-dupe preserve order
    seen: set[str] = set()
    out: list[str] = []
    for item in entities:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out[:8]


def heuristic_enrich(row: dict[str, Any]) -> dict[str, Any]:
    family = classify_hazard(row)
    severity_score = int(row.get("severity_rank") or 3)
    place = row.get("state_or_region") or row.get("area_desc") or "an unspecified area"
    if isinstance(place, str) and len(place) > 60:
        place = place[:57] + "..."
    name = row.get("event_name") or "Event"
    summary = f"{name} affecting {place}."
    return {
        "hazard_family": family,
        "severity_score": severity_score,
        "impact_summary": summary[:220],
        "recommended_audience": AUDIENCE_BY_SEVERITY.get(severity_score, "analyst"),
        "entities": extract_entities(row),
        "confidence": 0.55 if family != "other" else 0.35,
        "enricher": "heuristic",
        "model": "rules-v1",
        "prompt_version": "v1",
        "tokens_in": 0,
        "tokens_out": 0,
        "cost_usd": 0.0,
    }
