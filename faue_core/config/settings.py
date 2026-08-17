"""Base settings. Read once at startup; a missing required variable fails
immediately and loudly, not on first use at 3 a.m."""

from __future__ import annotations

from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings as PydanticBaseSettings
from pydantic_settings import SettingsConfigDict


class BaseSettings(PydanticBaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str
    environment: Literal["local", "staging", "prod"] = "local"
    database_url: SecretStr
    redis_url: SecretStr
    otel_exporter_otlp_endpoint: str | None = None
    log_level: str = "INFO"
