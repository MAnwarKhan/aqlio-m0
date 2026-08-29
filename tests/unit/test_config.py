from __future__ import annotations

import pytest

from app.config import Settings, SettingsError


def test_development_defaults_need_no_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "APP_ENV",
        "DATABASE_URL",
        "OBJECT_STORAGE_ENDPOINT",
        "OBJECT_STORAGE_BUCKET",
        "OPENAI_GENERATION_MODEL",
        "OPENAI_EMBEDDING_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = Settings.from_env()

    assert settings.app_env == "development"
    assert settings.auth_mode == "development"
    assert settings.ai_mode == "fake"


def test_pilot_configuration_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "pilot")
    monkeypatch.setenv("AQLIO_AUTH_MODE", "development")

    with pytest.raises(SettingsError, match="Google sign-in"):
        Settings.from_env()


def test_file_types_are_restricted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLOWED_FILE_TYPES", "pdf,exe")

    with pytest.raises(SettingsError, match="pdf, docx, and txt"):
        Settings.from_env()


def test_managed_mode_fails_closed_without_provider_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AQLIO_AI_MODE", "managed")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_GENERATION_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_EMBEDDING_MODEL", raising=False)

    with pytest.raises(SettingsError, match="OPENAI_API_KEY"):
        Settings.from_env()
