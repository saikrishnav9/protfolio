from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(ts: datetime | None = None) -> str:
    return (ts or utcnow()).isoformat()


class PipelineRun(BaseModel):
    run_id: str
    started_at: str
    finished_at: str | None = None
    status: str = "running"
    mode: str = "live"
    bronze_nws_rows: int = 0
    bronze_eonet_rows: int = 0
    bronze_weather_rows: int = 0
    silver_rows: int = 0
    gold_rows: int = 0
    tests_passed: bool | None = None
    tests_failed: list[str] = Field(default_factory=list)
    enricher: str = "heuristic"
    llm_called: bool = False
    llm_skipped_reason: str | None = None
    model: str | None = None
    prompt_version: str = "v1"
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    warnings: list[str] = Field(default_factory=list)
    git_sha: str | None = None

    def to_public_dict(self) -> dict[str, Any]:
        return self.model_dump()
