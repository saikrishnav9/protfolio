from __future__ import annotations

import json
import re
from typing import Any

import httpx
from pydantic import BaseModel, Field, ValidationError, field_validator

from pulse.config import Settings
from pulse.enrich.heuristic import heuristic_enrich

PROMPT_VERSION = "v1"

SYSTEM_PROMPT = """You are a data-engineering enrichment step, not a chatbot.
Return ONLY JSON with this schema:
{
  "hazard_family": "tornado|severe_weather|flood|winter|heat|wildfire|volcano|earthquake|marine|air_quality|other",
  "severity_score": 1,
  "impact_summary": "one sentence, max 220 chars",
  "recommended_audience": "emergency_ops|public|analyst",
  "entities": ["place or hazard names"],
  "confidence": 0.0
}
severity_score is 1-5. confidence is 0-1. Do not invent coordinates or casualties.
Ground every claim in the provided fields.
"""


class Enrichment(BaseModel):
    hazard_family: str
    severity_score: int = Field(ge=1, le=5)
    impact_summary: str
    recommended_audience: str
    entities: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)

    @field_validator("hazard_family")
    @classmethod
    def family_ok(cls, value: str) -> str:
        allowed = {
            "tornado",
            "severe_weather",
            "flood",
            "winter",
            "heat",
            "wildfire",
            "volcano",
            "earthquake",
            "marine",
            "air_quality",
            "other",
        }
        value = value.strip().lower().replace(" ", "_")
        if value not in allowed:
            return "other"
        return value

    @field_validator("recommended_audience")
    @classmethod
    def audience_ok(cls, value: str) -> str:
        value = value.strip().lower().replace(" ", "_")
        if value not in {"emergency_ops", "public", "analyst"}:
            return "analyst"
        return value

    @field_validator("impact_summary")
    @classmethod
    def clip_summary(cls, value: str) -> str:
        return value.strip()[:220]


class LLMProvider:
    def __init__(self, name: str, base_url: str, api_key: str, model: str, headers: dict[str, str] | None = None):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.headers = headers or {}

    def complete_json(self, user_prompt: str) -> tuple[dict[str, Any], int, int]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            **self.headers,
        }
        body = {
            "model": self.model,
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
        }
        with httpx.Client(timeout=45.0) as client:
            response = client.post(f"{self.base_url}/chat/completions", headers=headers, json=body)
            response.raise_for_status()
            payload = response.json()
        content = payload["choices"][0]["message"]["content"]
        usage = payload.get("usage") or {}
        tokens_in = int(usage.get("prompt_tokens") or 0)
        tokens_out = int(usage.get("completion_tokens") or 0)
        parsed = json.loads(_extract_json(content))
        return parsed, tokens_in, tokens_out


def _extract_json(text: str) -> str:
    text = text.strip()
    if text.startswith("{") and text.endswith("}"):
        return text
    match = re.search(r"\{.*\}", text, flags=re.S)
    if not match:
        raise ValueError("LLM did not return JSON")
    return match.group(0)


def select_provider(settings: Settings) -> LLMProvider | None:
    if settings.groq_api_key:
        return LLMProvider(
            name="groq",
            base_url="https://api.groq.com/openai/v1",
            api_key=settings.groq_api_key,
            model="llama-3.1-8b-instant",
        )
    if settings.gemini_api_key:
        return LLMProvider(
            name="gemini",
            base_url="https://generativelanguage.googleapis.com/v1beta/openai",
            api_key=settings.gemini_api_key,
            model="gemini-2.0-flash",
        )
    token = settings.github_token
    if settings.pulse_use_github_models and token:
        return LLMProvider(
            name="github_models",
            base_url="https://models.github.ai/inference",
            api_key=token,
            model="openai/gpt-4o-mini",
            headers={"Accept": "application/vnd.github+json"},
        )
    return None


def row_prompt(row: dict[str, Any]) -> str:
    context = {
        "event_name": row.get("event_name"),
        "source": row.get("source"),
        "severity_raw": row.get("severity_raw"),
        "severity_rank": row.get("severity_rank"),
        "category": row.get("category"),
        "area_desc": row.get("area_desc"),
        "state_or_region": row.get("state_or_region"),
        "headline": row.get("headline"),
        "description": (row.get("description") or "")[:900],
        "temperature_c": row.get("temperature_c"),
        "wind_speed_kmh": row.get("wind_speed_kmh"),
        "weather_city": row.get("weather_city"),
    }
    return "Enrich this warehouse row:\n" + json.dumps(context, default=str)


def llm_enrich(row: dict[str, Any], provider: LLMProvider) -> dict[str, Any]:
    parsed, tokens_in, tokens_out = provider.complete_json(row_prompt(row))
    model = Enrichment.model_validate(parsed)
    return {
        **model.model_dump(),
        "enricher": "llm",
        "model": f"{provider.name}:{provider.model}",
        "prompt_version": PROMPT_VERSION,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost_usd": 0.0,
    }


def enrich_row(row: dict[str, Any], provider: LLMProvider | None) -> dict[str, Any]:
    if provider is None:
        return heuristic_enrich(row)
    try:
        return llm_enrich(row, provider)
    except (httpx.HTTPError, ValidationError, json.JSONDecodeError, KeyError, ValueError):
        fallback = heuristic_enrich(row)
        fallback["enricher"] = "heuristic_fallback"
        return fallback
