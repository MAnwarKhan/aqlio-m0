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
