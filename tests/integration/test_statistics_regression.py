"""Run with AQLIO_STATISTICS_PDF pointing to the user-supplied course pack.

The uploaded PDF is deliberately not committed. CI still exercises synthetic cases
in test_question_aware_answering; this integration suite checks the original bytes.
"""

import os
from pathlib import Path

import pytest

from tests.helpers import build_service
from tests.integration.test_page_citations import publish

CEDAR = (
    "What is Cedar-7's sample variance, and why do we divide by 6? "
    "Please cite the page where you found the information."
)
SEABROOK = "What is Seabrook's exact correlation coefficient?"


@pytest.mark.parametrize("question", [CEDAR, SEABROOK])
def test_original_statistics_pdf_working_and_published(question):
    location = os.getenv("AQLIO_STATISTICS_PDF")
    if not location:
        pytest.skip("Set AQLIO_STATISTICS_PDF to the supplied course pack")
    pdf = Path(location)
    service = build_service()
    project = service.create_project("Statistics regression")
    service.add_and_prepare_document(project.id, pdf.name, pdf.read_bytes())
    working = service.ask_question(project.id, question)
    publication = publish(service, project.id, question)
    link = service.enable_link_sharing(publication.id)
    shared = service.ask_shared(link.token, question)
    for answer in (working, shared):
        assert not answer.abstained
        assert question not in answer.text
        if question == CEDAR:
            assert "48 / 6 = 8 min²" in answer.text
            assert "n \u2212 1" in answer.text
            assert "seven values as a sample" in answer.text
            assert {citation.page_number for citation in answer.citations} == {2}
        else:
            assert "does not report an exact correlation coefficient" in answer.text
            assert not any(char.isdigit() for char in answer.text)
            assert {citation.page_number for citation in answer.citations} == {7}


COMPARISON = "What is the difference between variance and standard deviation?"
FORMATTED = (
    "According to the document, what is the difference between variance and standard deviation? "
    "Please answer in 2\u20133 sentences and cite the page."
)


@pytest.mark.parametrize("question", [CEDAR, COMPARISON, FORMATTED])
def test_document_qa_regressions_working_and_published(monkeypatch, question):
    from types import SimpleNamespace

    from app.application import documents
    from tests.integration.test_page_citations import RecordingGeneration

    pages = [
        "PAGE TOPIC AND RETRIEVAL ANCHOR 2 Variance and standard deviation. "
        "Probability and neighboring topics.",
        "Variance and standard deviation\n"
        "Variance averages squared distances from the mean. "
        "Standard deviation is its square root and returns spread to the original units. "
        "Cedar-7 sample variance uses n \u2212 1 = 6 for seven values. "
        "Squared deviations total 48. Treat the seven values as a sample: 48 / 6 = 8 min².",
    ]
    monkeypatch.setattr(
        documents,
        "PdfReader",
        lambda _: SimpleNamespace(
            pages=[SimpleNamespace(extract_text=lambda text=text: text) for text in pages]
        ),
    )
    generation = RecordingGeneration()
    service = build_service(generation=generation)
    project = service.create_project("Statistics")
    service.add_and_prepare_document(project.id, "statistics.pdf", b"%PDF-stub")
    working = service.ask_question(project.id, question)
    publication = publish(service, project.id, question)
    link = service.enable_link_sharing(publication.id)
    shared = service.ask_shared(link.token, question)
    assert generation.requests[-1].question == question
    assert service._question_terms(COMPARISON) == service._question_terms(FORMATTED)
    for answer in (working, shared):
        assert not answer.abstained
        assert {c.page_number for c in answer.citations} == {2}
        if question == CEDAR:
            assert "48 / 6 = 8 min²" in answer.text
            assert "n \u2212 1 = 6" in answer.text
        else:
            assert answer.text == (
                "Variance averages squared distances from the mean. "
                "Standard deviation is its square root and returns spread to the original units."
            )
    for ask in (
        lambda q: service.ask_question(project.id, q),
        lambda q: service.ask_shared(link.token, q),
    ):
        missing = ask(
            "According to the document, what is the admission fee? "
            "Please answer in 2\u20133 sentences and cite the page."
        )
        assert missing.abstained and not missing.citations


@pytest.mark.parametrize("question", [COMPARISON, FORMATTED])
def test_original_pdf_comparison(question):
    location = os.getenv("AQLIO_STATISTICS_PDF")
    if not location:
        pytest.skip("Set AQLIO_STATISTICS_PDF to the supplied course pack")
    service = build_service()
    project = service.create_project("Statistics")
    service.add_and_prepare_document(project.id, "statistics.pdf", Path(location).read_bytes())
    working = service.ask_question(project.id, question)
    publication = publish(service, project.id, question)
    link = service.enable_link_sharing(publication.id)
    shared = service.ask_shared(link.token, question)
    for answer in (working, shared):
        assert answer.text == (
            "Variance averages squared distances from the mean. "
            "Standard deviation is its square root and returns spread to the original units."
        )
        assert not answer.abstained
        assert {c.page_number for c in answer.citations} == {2}
