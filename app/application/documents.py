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


def normalize_text(text: str) -> str:
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.replace("\x00", "").splitlines()]
    return "\n".join(line for line in lines if line).strip()


def chunk_text(text: str, *, max_words: int = 90) -> list[str]:
    words = text.split()
    return [" ".join(words[index : index + max_words]) for index in range(0, len(words), max_words)]


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
