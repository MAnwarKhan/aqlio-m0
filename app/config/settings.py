"""Typed, environment-backed settings with fail-closed pilot validation."""

from __future__ import annotations

import os
from dataclasses import dataclass


class SettingsError(ValueError):
    """Raised when runtime configuration is unsafe or incomplete."""


def _positive_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise SettingsError(f"{name} must be a whole number.") from exc
    if value <= 0:
        raise SettingsError(f"{name} must be greater than zero.")
    return value


def _nonnegative_float(name: str, default: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except ValueError as exc:
        raise SettingsError(f"{name} must be a number.") from exc
    if value < 0:
        raise SettingsError(f"{name} must not be negative.")
    return value


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings safe to pass to application composition code."""

    app_env: str
    app_base_url: str
    support_contact: str
    log_level: str
    auth_mode: str
    ai_mode: str
    daily_ai_request_allowance: int
    max_file_size_mb: int
    max_files_per_project: int
    max_project_storage_mb: int
    allowed_file_types: frozenset[str]
    persistence_mode: str = "in_memory"
    storage_mode: str = "in_memory"
    local_storage_path: str = "storage"
    upload_rate_limit: int = 20
    preparation_rate_limit: int = 20
    ai_rate_limit: int = 30
    shared_access_rate_limit: int = 60
    rate_limit_window_seconds: int = 60
    database_url: str | None = None
    object_storage_endpoint: str | None = None
    object_storage_bucket: str | None = None
    oidc_provider: str | None = None
    oidc_client_id: str | None = None
    oidc_client_secret: str | None = None
    oidc_redirect_uri: str | None = None
    object_storage_access_key_id: str | None = None
    object_storage_secret_access_key: str | None = None
    object_storage_region: str | None = None
    admin_emails: frozenset[str] = frozenset()
    openai_generation_model: str | None = None
    openai_embedding_model: str | None = None
    openai_api_key: str | None = None
    ai_timeout_seconds: int = 30
    ai_max_retries: int = 2
    generation_input_cost_per_million: float = 0.0
    generation_output_cost_per_million: float = 0.0
    embedding_input_cost_per_million: float = 0.0
    live_ai_tests_enabled: bool = False
    live_ai_test_max_calls: int = 4
    live_ai_test_max_estimated_cost: float = 0.10
    chunk_max_words: int = 90

    @classmethod
    def from_env(cls) -> Settings:
        allowed = frozenset(
            item.strip().lower()
            for item in os.getenv("ALLOWED_FILE_TYPES", "pdf,docx,txt").split(",")
            if item.strip()
        )
        settings = cls(
            app_env=os.getenv("APP_ENV", "development").lower(),
            app_base_url=os.getenv("APP_BASE_URL", "http://localhost:8501"),
            support_contact=os.getenv("SUPPORT_CONTACT", "support@example.com"),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            auth_mode=os.getenv("AQLIO_AUTH_MODE", "development").lower(),
            ai_mode=os.getenv("AQLIO_AI_MODE", "fake").lower(),
            daily_ai_request_allowance=_positive_int("DAILY_AI_REQUEST_ALLOWANCE", 25),
            max_file_size_mb=_positive_int("MAX_FILE_SIZE_MB", 10),
            max_files_per_project=_positive_int("MAX_FILES_PER_PROJECT", 5),
            max_project_storage_mb=_positive_int("MAX_PROJECT_STORAGE_MB", 25),
            allowed_file_types=allowed,
            persistence_mode=os.getenv("AQLIO_PERSISTENCE_MODE", "in_memory").lower(),
            storage_mode=os.getenv("AQLIO_STORAGE_MODE", "in_memory").lower(),
            local_storage_path=os.getenv("LOCAL_STORAGE_PATH", "storage"),
            upload_rate_limit=_positive_int("UPLOAD_RATE_LIMIT", 20),
            preparation_rate_limit=_positive_int("PREPARATION_RATE_LIMIT", 20),
            ai_rate_limit=_positive_int("AI_RATE_LIMIT", 30),
            shared_access_rate_limit=_positive_int("SHARED_ACCESS_RATE_LIMIT", 60),
            rate_limit_window_seconds=_positive_int("RATE_LIMIT_WINDOW_SECONDS", 60),
            database_url=os.getenv("DATABASE_URL"),
            object_storage_endpoint=os.getenv("OBJECT_STORAGE_ENDPOINT"),
            object_storage_bucket=os.getenv("OBJECT_STORAGE_BUCKET"),
            oidc_provider=os.getenv("OIDC_PROVIDER"),
            oidc_client_id=os.getenv("OIDC_CLIENT_ID"),
            oidc_client_secret=os.getenv("OIDC_CLIENT_SECRET"),
            oidc_redirect_uri=os.getenv("OIDC_REDIRECT_URI"),
            object_storage_access_key_id=os.getenv("OBJECT_STORAGE_ACCESS_KEY_ID"),
            object_storage_secret_access_key=os.getenv("OBJECT_STORAGE_SECRET_ACCESS_KEY"),
            object_storage_region=os.getenv("OBJECT_STORAGE_REGION"),
            admin_emails=frozenset(
                email.strip().lower()
                for email in os.getenv("ADMIN_EMAILS", "").split(",")
                if email.strip()
            ),
            openai_generation_model=os.getenv("OPENAI_GENERATION_MODEL"),
            openai_embedding_model=os.getenv("OPENAI_EMBEDDING_MODEL"),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            ai_timeout_seconds=_positive_int("AI_TIMEOUT_SECONDS", 30),
            ai_max_retries=int(os.getenv("AI_MAX_RETRIES", "2")),
            generation_input_cost_per_million=_nonnegative_float(
                "OPENAI_GENERATION_INPUT_COST_PER_MILLION", 0.0
            ),
            generation_output_cost_per_million=_nonnegative_float(
                "OPENAI_GENERATION_OUTPUT_COST_PER_MILLION", 0.0
            ),
            embedding_input_cost_per_million=_nonnegative_float(
                "OPENAI_EMBEDDING_INPUT_COST_PER_MILLION", 0.0
            ),
            live_ai_tests_enabled=os.getenv("LIVE_AI_TESTS_ENABLED", "false").lower() == "true",
            live_ai_test_max_calls=_positive_int("LIVE_AI_TEST_MAX_CALLS", 4),
            live_ai_test_max_estimated_cost=_nonnegative_float(
                "LIVE_AI_TEST_MAX_ESTIMATED_COST", 0.10
            ),
            chunk_max_words=_positive_int("DOCUMENT_CHUNK_MAX_WORDS", 90),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if self.auth_mode not in {"development", "oidc"}:
            raise SettingsError("AQLIO_AUTH_MODE must be development or oidc.")
        if self.ai_mode not in {"fake", "managed"}:
            raise SettingsError("AQLIO_AI_MODE must be fake or managed.")
        if self.ai_max_retries < 0:
            raise SettingsError("AI_MAX_RETRIES must not be negative.")
        if self.ai_mode == "managed":
            managed_required = {
                "OPENAI_API_KEY": self.openai_api_key,
                "OPENAI_GENERATION_MODEL": self.openai_generation_model,
                "OPENAI_EMBEDDING_MODEL": self.openai_embedding_model,
            }
            missing_managed = [name for name, value in managed_required.items() if not value]
            if missing_managed:
                names = ", ".join(sorted(missing_managed))
                raise SettingsError(f"Missing required managed AI settings: {names}.")
        if not self.allowed_file_types or not self.allowed_file_types <= {"pdf", "docx", "txt"}:
            raise SettingsError("ALLOWED_FILE_TYPES may contain only pdf, docx, and txt.")
        if self.persistence_mode not in {"in_memory", "sqlalchemy"}:
            raise SettingsError("AQLIO_PERSISTENCE_MODE must be in_memory or sqlalchemy.")
        if self.storage_mode not in {"in_memory", "local", "s3"}:
            raise SettingsError("AQLIO_STORAGE_MODE must be in_memory, local, or s3.")
        if self.app_env in {"pilot", "production"}:
            required = {
                "DATABASE_URL": self.database_url,
                "OBJECT_STORAGE_ENDPOINT": self.object_storage_endpoint,
                "OBJECT_STORAGE_BUCKET": self.object_storage_bucket,
                "OBJECT_STORAGE_ACCESS_KEY_ID": self.object_storage_access_key_id,
                "OBJECT_STORAGE_SECRET_ACCESS_KEY": self.object_storage_secret_access_key,
                "OIDC_CLIENT_ID": self.oidc_client_id,
                "OIDC_CLIENT_SECRET": self.oidc_client_secret,
                "OIDC_REDIRECT_URI": self.oidc_redirect_uri,
            }
            if self.auth_mode != "oidc" or self.oidc_provider != "google":
                raise SettingsError("Pilot authentication must use the configured Google sign-in.")
            if self.persistence_mode != "sqlalchemy":
                raise SettingsError("Pilot persistence must use the durable database adapter.")
            if self.storage_mode != "s3":
                raise SettingsError("Pilot document storage must use private storage.")
            missing = [name for name, value in required.items() if not value]
            if missing:
                missing_names = ", ".join(sorted(missing))
                raise SettingsError(f"Missing required pilot settings: {missing_names}.")
