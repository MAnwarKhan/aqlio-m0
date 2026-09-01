"""Structured logging helpers that redact sensitive fields."""

import json
import logging
from collections.abc import Mapping
from typing import Any

_SENSITIVE_FRAGMENTS = (
    "answer",
    "authorization",
    "content",
    "credential",
    "document_text",
    "prompt",
    "secret",
    "signed_url",
    "token",
)


def redact(fields: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: "[REDACTED]" if any(part in key.lower() for part in _SENSITIVE_FRAGMENTS) else value
        for key, value in fields.items()
    }


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        fields = getattr(record, "fields", None)
        if isinstance(fields, Mapping):
            payload["fields"] = redact(fields)
        return json.dumps(payload, default=str, separators=(",", ":"))


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
