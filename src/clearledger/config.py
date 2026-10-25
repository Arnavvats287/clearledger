from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

from clearledger.advanced_domain import Limits


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    database_url: str
    organization_id: UUID | None = None
    matching_limits: Limits = Limits()
    document_root: Path = Path("local-data/documents")
    document_api_token: SecretStr | None = None
    case_read_token: SecretStr | None = None
    case_outbox_max_attempts: int = Field(default=3, ge=1, le=10)
    case_outbox_lease_seconds: int = Field(default=30, ge=5, le=300)
    extraction_provider: Literal["disabled", "gemini", "fake"] = "disabled"
    external_ai_enabled: bool = False
    privacy_review_reference: str = ""
    gemini_api_key: SecretStr | None = None
    gemini_model: str = ""
    llm_timeout_ms: int = Field(default=10000, ge=100, le=30000)
    llm_attempts: int = Field(default=2, ge=1, le=3)
    llm_requests_per_minute: int = Field(default=10, ge=1, le=60)
    llm_shared_requests_per_minute: int = Field(default=30, ge=0, le=180)
    llm_daily_requests: int = Field(default=30, ge=0, le=10000)
    llm_daily_input_tokens: int = Field(default=100000, ge=0, le=100000000)
    llm_daily_output_tokens: int = Field(default=30000, ge=0, le=100000000)
    llm_max_input_tokens: int = Field(default=8192, ge=1, le=1000000)
    llm_max_output_tokens: int = Field(default=4096, ge=1, le=4096)
    llm_max_cost_paise_per_attempt: int | None = Field(default=None, ge=0)
    llm_input_paise_per_million_tokens: int | None = Field(default=None, ge=0)
    llm_output_paise_per_million_tokens: int | None = Field(default=None, ge=0)

    @field_validator("database_url")
    @classmethod
    def require_postgresql(cls, value: str) -> str:
        if make_url(value).drivername != "postgresql+psycopg":
            raise ValueError("DATABASE_URL must use postgresql+psycopg")
        return value
