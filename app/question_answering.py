"""Deterministic, question-aware selection of grounded document evidence."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from app.ports.contracts import Citation, GenerationResponse, RetrievedContext

_STOPWORDS = {
    "a",
    "about",
    "all",
    "an",
    "and",
    "are",
    "complete",
    "does",
    "every",
    "from",
    "give",
    "how",
    "in",
    "is",
    "it",
    "list",
    "me",
    "of",
    "please",
    "provide",
    "show",
    "the",
    "to",
    "what",
    "when",
    "where",
    "which",
    "who",
    "with",
}
_LIST_TERMS = {"all", "complete", "every", "list"}
_SUMMARY_TERMS = {"overview", "summarize", "summary"}
_COMPARISON_TERMS = {"compare", "comparison", "difference", "different", "versus", "vs"}


@dataclass(frozen=True, slots=True)
class _Unit:
    text: str
    context: RetrievedContext
    score: int


def substantive_question(question: str) -> str:
    """Remove bounded presentation clauses without discarding the information need."""
    subject = re.sub(
        r"\baccording to (?:the |this |provided |supplied )?documents?\s*,?\s*",
        "",
        question,
        flags=re.IGNORECASE,
    )
    subject = re.sub(
        r"\b(?:please\s+)?(?:answer|respond)(?:\s+in)?\s+"
        r"(?:\d+|one|two|three)(?:\s*[-\u2013\u2014]\s*(?:\d+|one|two|three))?"
        r"\s+sentences?\b",
        "",
        subject,
        flags=re.IGNORECASE,
    )
    subject = re.sub(
        r"\b(?:please\s+)?cite\s+(?:the |a |your )?"
        r"(?:pages?|sources?)(?:\s+where you found (?:the )?information)?\b",
        "",
        subject,
        flags=re.IGNORECASE,
    )
    return subject.strip(" ,.;")


def _comparison_units(question: str, units: Sequence[_Unit]) -> list[tuple[str, RetrievedContext]]:
    # Identify both subjects, then select a declarative sentence led by each subject.
    # Headings, indexes, exercises, and incidental mentions are not definitions.
    match = re.search(
        r"(?:between|compare|comparison of)\s+(.+?)\s+"
        r"(?:and|versus|vs\.?)\s+(.+?)(?:[?.!]|$)",
        question,
        re.IGNORECASE,
    )
    if not match:
        return []
    output: list[tuple[str, RetrievedContext]] = []
    for subject in match.groups():
        words = subject.strip().split()
        candidates = []
        # A trailing shared attribute (e.g. 'Basic versus Premium support') is optional.
        for length in range(len(words), 0, -1):
            prefix = r"^(?:The\s+)?" + r"\s+".join(re.escape(w) for w in words[:length])
            candidates = [
                unit
                for unit in units
                if re.search(
                    prefix + r"(?:\s+\w+){0,2}\s+(?:is|are|has|have|uses?|includes?|"
                    r"measures?|averages?|means?|expresses?|provides?|costs?)\b",
                    unit.text,
                    re.IGNORECASE,
                )
                and unit.text.endswith((".", "!"))
            ]
            if candidates:
                break
        if not candidates:
            return []
        best = candidates[0]
        output.append((best.text, best.context))
    return list(dict.fromkeys(output))


def grounded_fake_answer(question: str, context: Sequence[RetrievedContext]) -> GenerationResponse:
    """Produce a responsive deterministic answer instead of surfacing retrieval text."""
    if not context:
        return _abstention()
    question = substantive_question(question)
    intent = _intent(question)
    focus = _terms(question) - _STOPWORDS - _LIST_TERMS - _SUMMARY_TERMS - _COMPARISON_TERMS
    units = [
        _Unit(text, item, len(focus & _terms(text)))
        for item in context
        for text in _units(
            "\n".join(
                line for line in item.text.splitlines() if not (_terms(line) - _STOPWORDS) <= focus
            )
            if intent == "comparison"
            else item.text
        )
    ]
    responsive = [unit for unit in units if unit.score > 0 and "?" not in unit.text]
    if not responsive:
        return _abstention()
    responsive.sort(key=lambda unit: (-unit.score, len(unit.text.split())))
    if intent == "list":
        answer_units = _list_answer_units(responsive)
        answer = "\n".join(f"- {text}" for text, _context in answer_units)
    elif intent == "summary":
        answer_units = [(unit.text, unit.context) for unit in responsive[:4]]
        answer = " ".join(text for text, _context in answer_units)
    elif intent == "comparison":
        answer_units = _comparison_units(question, units)
        answer = " ".join(text for text, _context in answer_units)
    else:
        best = responsive[0]
        if "why" in _terms(question):
            # Explanations often span sentences/table rows and neighboring chunks.
            selected = (
                [
                    item
                    for item in context
                    if item.document_id == best.context.document_id
                    and item.page_number == best.context.page_number
                ]
                if best.context.page_number is not None
                else [best.context]
            )
            selected = selected[selected.index(best.context) :][:2]
            passage = " ".join(
                text for text in _units(" ".join(item.text for item in selected)) if "?" not in text
            )
            answer_units = [(passage, item) for item in selected]
        else:
            answer_units = [(best.text, best.context)]
        answer = " ".join(dict.fromkeys(text for text, _context in answer_units))
    if not answer.strip() or not answer_units:
        return _abstention()
    used = {item.chunk_id: item for _text, item in answer_units}
    return GenerationResponse(
        answer,
        tuple(
            Citation(item.document_name, item.chunk_id, item.page_number) for item in used.values()
        ),
    )


def _abstention() -> GenerationResponse:
    return GenerationResponse(
        "I couldn't establish that from the documents provided.", (), abstained=True
    )


def _intent(question: str) -> str:
    terms = _terms(question)
    if terms & _LIST_TERMS:
        return "list"
    if terms & _SUMMARY_TERMS:
        return "summary"
    if terms & _COMPARISON_TERMS:
        return "comparison"
    return "fact"


def _terms(text: str) -> set[str]:
    output: set[str] = set()
    for raw in re.findall(r"[a-z0-9]+", text.lower()):
        if len(raw) <= 2:
            continue
        term = raw[:-3] + "y" if raw.endswith("ies") and len(raw) > 4 else raw
        if term.endswith("s") and not term.endswith("ss") and len(term) > 4:
            term = term[:-1]
        output.add(term)
    return output


def _units(text: str) -> list[str]:
    units: list[str] = []
    # PDF visual line breaks are not sentence boundaries. Preserve actual lists.
    text = re.sub(r"(?<![.!?:])\n(?!\s*(?:[-*•]|\d+[.)])\s)", " ", text)
    for line in text.splitlines():
        clean = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", line).strip()
        if clean:
            units.extend(part.strip() for part in re.split(r"(?<=[.!?])\s+", clean) if part.strip())
    return units


def _list_answer_units(responsive: Sequence[_Unit]) -> list[tuple[str, RetrievedContext]]:
    best_score = responsive[0].score
    selected = [unit for unit in responsive if unit.score == best_score]
    output: list[tuple[str, RetrievedContext]] = []
    for unit in selected:
        if unit.text.endswith(":"):
            lines = unit.context.text.splitlines()
            for index, line in enumerate(lines):
                if line.strip() != unit.text:
                    continue
                for following in lines[index + 1 :]:
                    bullet = re.match(r"^\s*(?:[-*•]|\d+[.)])\s+(.+?)\s*$", following)
                    if not bullet:
                        break
                    output.append((bullet.group(1).rstrip("."), unit.context))
                break
            if output:
                continue
        match = re.search(
            r"(?:\b(?:are|include|includes|comprise|comprises|consist of)\b|:)\s*(.+)$",
            unit.text,
            re.IGNORECASE,
        )
        candidate = match.group(1) if match else unit.text
        pieces = re.split(r"\s*,\s*|\s+and\s+|\s*;\s*", candidate.rstrip(". "))
        meaningful = [
            re.sub(r"^and\s+", "", piece.strip(" -•"), flags=re.IGNORECASE)
            for piece in pieces
            if piece.strip(" -•")
        ]
        if len(meaningful) > 1:
            output.extend((piece, unit.context) for piece in meaningful)
        else:
            output.append((candidate.strip(), unit.context))
    return list(dict.fromkeys(output))
