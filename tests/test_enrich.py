from pulse.enrich.heuristic import classify_hazard, heuristic_enrich
from pulse.enrich.llm import Enrichment


def test_tornado_family():
    row = {
        "event_name": "Tornado Warning",
        "headline": "Tornado Warning issued for Harris",
        "category": "Met",
        "description": "A confirmed tornado is on the ground.",
        "area_desc": "Harris; Fort Bend",
        "state_or_region": "TX",
        "severity_rank": 5,
    }
    assert classify_hazard(row) == "tornado"
    extra = heuristic_enrich(row)
    assert extra["recommended_audience"] == "emergency_ops"
    assert extra["enricher"] == "heuristic"
    assert extra["cost_usd"] == 0.0


def test_enrichment_schema_clips_and_defaults():
    parsed = Enrichment.model_validate(
        {
            "hazard_family": "space_junk",
            "severity_score": 4,
            "impact_summary": "x" * 500,
            "recommended_audience": "everyone",
            "entities": ["TX"],
            "confidence": 0.9,
        }
    )
    assert parsed.hazard_family == "other"
    assert parsed.recommended_audience == "analyst"
    assert len(parsed.impact_summary) == 220
