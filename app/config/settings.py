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
    database_url: str | None = None
    object_storage_endpoint: str | None = None
    object_storage_bucket: str | None = None
    oidc_provider: str | None = None
    openai_generation_model: str | None = None
    openai_embedding_model: str | None = None

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
            database_url=os.getenv("DATABASE_URL"),
            object_storage_endpoint=os.getenv("OBJECT_STORAGE_ENDPOINT"),
            object_storage_bucket=os.getenv("OBJECT_STORAGE_BUCKET"),
            oidc_provider=os.getenv("OIDC_PROVIDER"),
            openai_generation_model=os.getenv("OPENAI_GENERATION_MODEL"),
            openai_embedding_model=os.getenv("OPENAI_EMBEDDING_MODEL"),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if self.auth_mode not in {"development", "oidc"}:
            raise SettingsError("AQLIO_AUTH_MODE must be development or oidc.")
        if self.ai_mode not in {"fake", "managed"}:
            raise SettingsError("AQLIO_AI_MODE must be fake or managed.")
        if not self.allowed_file_types or not self.allowed_file_types <= {"pdf", "docx", "txt"}:
            raise SettingsError("ALLOWED_FILE_TYPES may contain only pdf, docx, and txt.")
        if self.app_env in {"pilot", "production"}:
            required = {
                "DATABASE_URL": self.database_url,
                "OBJECT_STORAGE_ENDPOINT": self.object_storage_endpoint,
                "OBJECT_STORAGE_BUCKET": self.object_storage_bucket,
            }
            if self.auth_mode != "oidc" or self.oidc_provider != "google":
                raise SettingsError("Pilot authentication must use the configured Google sign-in.")
            if self.ai_mode != "managed":
                raise SettingsError("Pilot AI mode must be managed.")
            if not self.openai_generation_model or not self.openai_embedding_model:
                required["OPENAI_GENERATION_MODEL"] = self.openai_generation_model
                required["OPENAI_EMBEDDING_MODEL"] = self.openai_embedding_model
            missing = [name for name, value in required.items() if not value]
            if missing:
                missing_names = ", ".join(sorted(missing))
                raise SettingsError(f"Missing required pilot settings: {missing_names}.")
