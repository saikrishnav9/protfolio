from __future__ import annotations

from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential_jitter

from pulse.config import Settings


def _client(settings: Settings, timeout: float = 30.0) -> httpx.Client:
    return httpx.Client(
        timeout=timeout,
        headers={
            "User-Agent": settings.user_agent,
            "Accept": "application/geo+json, application/json",
        },
        follow_redirects=True,
    )


@retry(stop=stop_after_attempt(3), wait=wait_exponential_jitter(initial=1, max=8))
def get_json(settings: Settings, url: str, params: dict[str, Any] | None = None) -> Any:
    with _client(settings) as client:
        response = client.get(url, params=params)
        response.raise_for_status()
        return response.json()


def fetch_nws_alerts(settings: Settings) -> dict[str, Any]:
    return get_json(settings, "https://api.weather.gov/alerts/active?status=actual")


def fetch_eonet_events(settings: Settings) -> dict[str, Any]:
    return get_json(settings, "https://eonet.gsfc.nasa.gov/api/v3/events", {"days": 14, "status": "open"})


WEATHER_CITIES: list[tuple[str, float, float]] = [
    ("New York", 40.7128, -74.0060),
    ("Chicago", 41.8781, -87.6298),
    ("Houston", 29.7604, -95.3698),
    ("Phoenix", 33.4484, -112.0740),
    ("Seattle", 47.6062, -122.3321),
    ("Denver", 39.7392, -104.9903),
    ("Miami", 25.7617, -80.1918),
    ("Minneapolis", 44.9778, -93.2650),
]


def fetch_weather_snapshots(settings: Settings) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, lat, lon in WEATHER_CITIES:
        payload = get_json(
            settings,
            "https://api.open-meteo.com/v1/forecast",
            {
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,wind_speed_10m,precipitation,weather_code",
                "timezone": "UTC",
            },
        )
        current = payload.get("current") or {}
        rows.append(
            {
                "city": name,
                "latitude": lat,
                "longitude": lon,
                "observed_at": current.get("time"),
                "temperature_c": current.get("temperature_2m"),
                "wind_speed_kmh": current.get("wind_speed_10m"),
                "precipitation_mm": current.get("precipitation"),
                "weather_code": current.get("weather_code"),
                "raw": payload,
            }
        )
    return rows
