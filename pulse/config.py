from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    pulse_offline: bool = False
    pulse_max_enrich_rows: int = 80
    pulse_use_github_models: bool = False
    groq_api_key: str = ""
    gemini_api_key: str = ""
    github_token: str = ""
    user_agent: str = "PulseLakehouse/0.1 (portfolio; https://github.com)"

    @property
    def data_dir(self) -> Path:
        return ROOT / "data"

    @property
    def bronze_dir(self) -> Path:
        return self.data_dir / "bronze"

    @property
    def fixtures_dir(self) -> Path:
        return ROOT / "fixtures"

    @property
    def dbt_dir(self) -> Path:
        return ROOT / "dbt"

    @property
    def dashboard_data_dir(self) -> Path:
        return ROOT / "dashboard" / "data"


def get_settings() -> Settings:
    return Settings()
