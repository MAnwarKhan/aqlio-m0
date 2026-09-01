from app.infrastructure.logging import redact


def test_sensitive_structured_fields_are_redacted() -> None:
    fields = redact(
        {
            "project_id": "project-1",
            "prompt": "private question",
            "document_text": "private content",
            "provider_status": "failed",
        }
    )

    assert fields["project_id"] == "project-1"
    assert fields["provider_status"] == "failed"
    assert fields["prompt"] == "[REDACTED]"
    assert fields["document_text"] == "[REDACTED]"
