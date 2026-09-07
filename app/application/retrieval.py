"""Expand ranked matches with bounded, same-page reference context."""

from collections.abc import Sequence

from app.application.documents import remove_untrusted_instruction_chunks
from app.domain.models import DocumentChunk, PublishedChunk


def with_neighbors[T: (DocumentChunk, PublishedChunk)](
    matches: Sequence[T], candidates: Sequence[T]
) -> list[T]:
    safe_texts = set(remove_untrusted_instruction_chunks([chunk.text for chunk in candidates]))
    by_position = {
        (chunk.asset_id, chunk.position): chunk for chunk in candidates if chunk.text in safe_texts
    }
    selected: dict[tuple[str, int], T] = {}
    for chunk in matches[:3]:
        if chunk.text not in safe_texts:
            continue
        selected[(chunk.asset_id, chunk.position)] = chunk
        for offset in (-1, 1):
            neighbor = by_position.get((chunk.asset_id, chunk.position + offset))
            if neighbor is not None and neighbor.page_number == chunk.page_number:
                selected[(neighbor.asset_id, neighbor.position)] = neighbor
    return sorted(selected.values(), key=lambda chunk: (chunk.asset_id, chunk.position))
