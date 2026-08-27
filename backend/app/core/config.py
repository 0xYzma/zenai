from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    zenai_mode: Literal["standalone", "integrated"] = "standalone"
    zenai_database_url: str = "postgresql+asyncpg://user:password@localhost:5432/zenai_db"
    target_database_url: str = "postgresql+asyncpg://user:password@localhost:5432/client_db"
    gemini_api_key: str = ""
    redis_url: str = "redis://localhost:6379/0"
    require_redis_for_readiness: bool = False  # Set true via env in integrated/production
    chroma_persist_dir: str = "./chroma_data"
    jwt_secret: str = "zenai-dev-secret-change-in-production"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    zenai_debug: bool = False
    zenai_encryption_key: str = ""
    saas_delegation_public_key: str = ""
    saas_delegation_issuer: str = "nexdokandar-backend"
    saas_delegation_audience: str = "nexdokandar-ai"
    saas_delegation_max_age_seconds: int = 300
    saas_delegation_clock_skew_seconds: int = 10
    saas_internal_tools_url: str = ""
    saas_internal_service_key: str = ""
    saas_analytics_database_url: str = ""
    enable_curated_tools: bool = False
    enable_text_to_sql: bool = False
    max_tool_calls_per_request: int = 4
    max_question_length: int = 2000
    ai_result_row_limit: int = 500
    ai_query_timeout_ms: int = 30000
    conversation_retention_days: int = 30
    audit_retention_days: int = 90

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        populate_by_name = True
        extra = "ignore"

    @property
    def is_integrated(self) -> bool:
        return self.zenai_mode == "integrated"

    @property
    def debug(self) -> bool:
        return self.zenai_debug

    def validate_runtime_configuration(self) -> None:
        """Fail fast when integrated mode is missing trust-boundary settings."""
        if not self.is_integrated:
            return

        missing = []
        if not self.saas_delegation_public_key.strip():
            missing.append("SAAS_DELEGATION_PUBLIC_KEY")
        if not self.saas_internal_service_key.strip():
            missing.append("SAAS_INTERNAL_SERVICE_KEY")
        if self.enable_curated_tools and not self.saas_internal_tools_url.strip():
            missing.append("SAAS_INTERNAL_TOOLS_URL")
        if self.enable_text_to_sql and not self.saas_analytics_database_url.strip():
            missing.append("SAAS_ANALYTICS_DATABASE_URL")

        if missing:
            raise RuntimeError(
                "Missing required integrated-mode settings: " + ", ".join(missing)
            )
        if self.saas_delegation_max_age_seconds <= 0:
            raise RuntimeError("SAAS_DELEGATION_MAX_AGE_SECONDS must be positive")
        if self.max_tool_calls_per_request <= 0:
            raise RuntimeError("MAX_TOOL_CALLS_PER_REQUEST must be positive")
        if self.ai_query_timeout_ms <= 0:
            raise RuntimeError("AI_QUERY_TIMEOUT_MS must be positive")


@lru_cache
def get_settings() -> Settings:
    return Settings()
