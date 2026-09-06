from types import SimpleNamespace

import pytest

from app.application import documents
from app.application.errors import ValidationError
from tests.helpers import build_service


def test_pdf_repairs_are_targeted_and_do_not_change_other_formats(monkeypatch):
    raw = "documentaFon invenFons informaFon Plalorm ﬁle ﬂow FooBar F-test platform"
    monkeypatch.setattr(
        documents,
        "PdfReader",
        lambda _: SimpleNamespace(pages=[SimpleNamespace(extract_text=lambda: raw)]),
    )
    fixed = documents.extract_text("sample.pdf", b"%PDF-stub")
    assert fixed == "documentation inventions information Platform file flow FooBar F-test platform"
    assert documents.extract_text("sample.txt", raw.encode()) == raw
    assert documents.normalize_pdf_text("xdocumentaFon customPlalorm informaFon_id") == (
        "xdocumentaFon customPlalorm informaFon_id"
    )


def test_true_txt_is_clean_and_rtf_masquerading_as_txt_is_rejected() -> None:
    content = b"Clean plain text.\nSecond line."
    name, media_type = documents.validate_document(
        filename="notes.txt",
        content=content,
        allowed_types=frozenset({"txt"}),
        max_size_bytes=1024,
    )
    assert (name, media_type) == ("notes.txt", "text/plain")
    assert documents.extract_text(name, content) == "Clean plain text.\nSecond line."

    disguised_rtf = b"{\\rtf1\\ansi{\\fonttbl{\\f0 Helvetica;}}\\cocoatextscaling0 Raw}"
    with pytest.raises(ValidationError, match="contains RTF formatting"):
        documents.validate_document(
            filename="disguised.txt",
            content=disguised_rtf,
            allowed_types=frozenset({"txt"}),
            max_size_bytes=1024,
        )


def test_pdf_repairs_reach_grounded_answers_without_mutating_publication(monkeypatch):
    raw = "The Plalorm stores documentaFon about invenFons and informaFon."
    monkeypatch.setattr(
        documents,
        "PdfReader",
        lambda _: SimpleNamespace(pages=[SimpleNamespace(extract_text=lambda: raw)]),
    )
    service = build_service()
    project = service.create_project("PDF example")
    service.add_and_prepare_document(project.id, "sample.pdf", b"%PDF-stub")
    answer = service.ask_question(project.id, "What information is stored?", guided=True)
    assert "documentation" in answer.text and "inventions" in answer.text
    assert "informaFon" not in answer.text and answer.citations
    service.confirm_test_success(project.id, answer.correlation_id)
    # Successful testing is sufficient; Run is now a peer action rather than a publishing gate.
    publication = service.publish_working_application(project.id)
    asset = service.list_documents(project.id)[0]
    service.prepare_document(project.id, asset.id, refresh=True)
    assert service.get_my_project(project.id).guided_test_count == 0
    assert service.get_my_project(project.id).current_version_id != publication.project_version_id
    assert service.repository.get_publication(publication.id) == publication
