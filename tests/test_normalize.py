from pulse.ingest.normalize import normalize_eonet_event, normalize_nws_feature
from pulse.models import iso


def test_nws_centroid_and_state():
    feature = {
        "id": "x",
        "geometry": {"type": "Point", "coordinates": [-95.37, 29.76]},
        "properties": {
            "id": "abc",
            "event": "Tornado Warning",
            "severity": "Extreme",
            "headline": "Tornado Warning for Harris County",
            "areaDesc": "Harris; Fort Bend",
            "geocode": {"UGC": ["TXC201"]},
            "onset": "2026-09-20T18:00:00+00:00",
            "description": "Confirmed tornado.",
        },
    }
    row = normalize_nws_feature(feature, iso())
    assert row["event_id"].startswith("nws:")
    assert row["state_or_region"] == "TX"
    assert row["severity_rank"] == 5
    assert round(row["latitude"], 2) == 29.76
    assert round(row["longitude"], 2) == -95.37


def test_eonet_point():
    event = {
        "id": "EONET_1",
        "title": "Wildfires - Northern California",
        "description": "Fire",
        "categories": [{"id": "wildfires", "title": "Wildfires"}],
        "geometry": [{"date": "2026-09-18T00:00:00Z", "type": "Point", "coordinates": [-121.5, 40.1]}],
    }
    row = normalize_eonet_event(event, iso())
    assert row["source"] == "eonet"
    assert row["latitude"] == 40.1
    assert row["longitude"] == -121.5
