"""Safe local document validation, extraction, normalization, and chunking."""

from __future__ import annotations

import io
import re
from collections.abc import Sequence
from pathlib import PurePath

from docx import Document
from pypdf import PdfReader

from app.application.errors import PreparationError, ValidationError

_MEDIA_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "txt": "text/plain",
}


def _looks_like_rtf(content: bytes) -> bool:
    sample = content[:4096].lstrip().lower()
    return sample.startswith(b"{\\rtf") or (
        b"\\fonttbl" in sample and b"\\cocoatextscaling" in sample
    )


def validate_document(
    *,
    filename: str,
    content: bytes,
    allowed_types: frozenset[str],
    max_size_bytes: int,
) -> tuple[str, str]:
    """Validate extension, size, signature, and return safe display/media values."""

    display_name = PurePath(filename.replace("\\", "/")).name.strip()
    if not display_name or display_name in {".", ".."}:
        raise ValidationError("Choose a document with a valid filename.")
    extension = display_name.rsplit(".", 1)[-1].lower() if "." in display_name else ""
    if extension not in allowed_types:
        raise ValidationError("This document type isn't supported. Add a PDF, DOCX, or TXT file.")
    if not content:
        raise ValidationError("This document is empty. Choose a document that contains text.")
    if len(content) > max_size_bytes:
        raise ValidationError("This document is too large. Choose a smaller file and try again.")
    if extension == "pdf" and not content.startswith(b"%PDF-"):
        raise ValidationError("This PDF does not appear to be a valid document.")
    if extension == "docx" and not content.startswith(b"PK"):
        raise ValidationError("This DOCX does not appear to be a valid document.")
    if extension == "txt":
        if _looks_like_rtf(content):
            raise ValidationError(
                "This .txt file contains RTF formatting. Save it as plain UTF-8 text and try again."
            )
        try:
            content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValidationError("This text file must use UTF-8 text encoding.") from exc
    return display_name, _MEDIA_TYPES[extension]


def extract_text(filename: str, content: bytes) -> str:
    extension = filename.rsplit(".", 1)[-1].lower()
    try:
        if extension == "txt":
            text = content.decode("utf-8")
        elif extension == "docx":
            document = Document(io.BytesIO(content))
            text = "\n".join(paragraph.text for paragraph in document.paragraphs)
        elif extension == "pdf":
            reader = PdfReader(io.BytesIO(content))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
            text = normalize_pdf_text(text)
        else:
            raise PreparationError(
                "We couldn't prepare this document. Add a PDF, DOCX, or TXT file."
            )
    except PreparationError:
        raise
    except Exception as exc:
        raise PreparationError(
            "We couldn't read this document. Check the file and try again."
        ) from exc
    normalized = normalize_text(text)
    if not normalized:
        raise PreparationError("We couldn't find usable text in this document.")
    return normalized


def normalize_pdf_text(text: str) -> str:
    """Repair reported whole-word extraction artifacts, never arbitrary F/l characters.

    Without the source PDF these are conservative lexical repairs, not font-map recovery.
    Keep this PDF-specific so literal TXT/DOCX identifiers are not rewritten.
    """
    ligatures = dict(zip("ﬀﬁﬂﬃﬄﬅﬆ", ("ff", "fi", "fl", "ffi", "ffl", "st", "st"), strict=True))
    text = text.translate(
        {ord(character): replacement for character, replacement in ligatures.items()}
    )
    repairs = {
        "documentaFon": "documentation",
        "invenFons": "inventions",
        "informaFon": "information",
        "Plalorm": "Platform",
    }
    repairs.update(
        {
            word[0].upper() + word[1:]: fixed[0].upper() + fixed[1:]
            for word, fixed in list(repairs.items())
        }
    )
    return re.sub(
        r"\b(?:" + "|".join(map(re.escape, repairs)) + r")\b",
        lambda match: repairs[match.group()],
        text,
    )


def normalize_text(text: str) -> str:
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.replace("\x00", "").splitlines()]
    return "\n".join(line for line in lines if line).strip()


def chunk_text(text: str, *, max_words: int = 90) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    count = 0
    for line in text.splitlines():
        words = line.split()
        while words:
            available = max_words - count
            current.append(" ".join(words[:available]))
            count += min(len(words), available)
            words = words[available:]
            if count == max_words:
                chunks.append("\n".join(current))
                current, count = [], 0
    if current:
        chunks.append("\n".join(current))
    return chunks


def remove_untrusted_instruction_chunks(chunks: Sequence[str]) -> list[str]:
    """Exclude likely operational instructions from the reference candidate set."""

    dangerous = (
        "ignore previous",
        "ignore all previous",
        "system prompt",
        "reveal secret",
        "reveal credential",
        "bypass permission",
        "change visibility",
        "access another project",
    )
    return [chunk for chunk in chunks if not any(term in chunk.lower() for term in dangerous)]
