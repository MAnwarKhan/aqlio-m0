from app.ports.contracts import RetrievedContext
from app.question_answering import grounded_fake_answer


def context(name: str, chunk: str, text: str) -> RetrievedContext:
    return RetrievedContext(f"doc-{chunk}", name, chunk, text)


def test_specific_fact_selects_only_responsive_evidence_and_its_citation() -> None:
    evidence = [
        context(
            "staff-guide.txt",
            "leave-fact",
            "Annual leave becomes available after 90 days of employment.\n"
            "Benefits include annual leave, sick leave, and parental leave.",
        ),
        context("locations.txt", "office", "The main office is in Portland."),
    ]

    result = grounded_fake_answer("When does annual leave become available?", evidence)

    assert result.answer == "Annual leave becomes available after 90 days of employment."
    assert "sick leave" not in result.answer
    assert result.citations == (result.citations[0],)
    assert result.citations[0].chunk_id == "leave-fact"


def test_complete_list_returns_matching_items_without_surrounding_text() -> None:
    evidence = [
        context(
            "service-catalog.txt",
            "services",
            "The studio opened in 2019.\nAvailable services:\n"
            "- Portrait photography\n- Product photography\n- Event photography\n"
            "Appointments require a deposit.",
        ),
        context("parking.txt", "parking", "Customer parking is behind the building."),
    ]

    result = grounded_fake_answer("Provide a complete list of available services.", evidence)

    assert result.answer.splitlines() == [
        "- Portrait photography",
        "- Product photography",
        "- Event photography",
    ]
    assert "2019" not in result.answer and "deposit" not in result.answer
    assert [citation.chunk_id for citation in result.citations] == ["services"]


def test_inline_list_generalizes_and_unsupported_question_abstains() -> None:
    evidence = [
        context(
            "course-guide.txt",
            "courses",
            "Available workshops include ceramics, printmaking, and watercolor. "
            "The reception desk closes at 6 PM.",
        )
    ]

    listed = grounded_fake_answer("List every available workshop.", evidence)
    unsupported = grounded_fake_answer("Who founded the organization?", evidence)

    assert listed.answer.splitlines() == ["- ceramics", "- printmaking", "- watercolor"]
    assert "reception" not in listed.answer
    assert unsupported.abstained and not unsupported.citations


def test_summary_and_comparison_use_task_appropriate_structure() -> None:
    evidence = [
        context("plans.txt", "basic", "Basic plan includes email support."),
        context("plans.txt", "premium", "Premium plan includes phone support."),
    ]

    summary = grounded_fake_answer("Summarize plan support.", evidence)
    comparison = grounded_fake_answer("Compare Basic versus Premium support.", evidence)

    assert summary.answer == (
        "Basic plan includes email support. Premium plan includes phone support."
    )
    assert comparison.answer.splitlines() == [
        "- Basic plan includes email support.",
        "- Premium plan includes phone support.",
    ]
    assert len(comparison.citations) == 2
