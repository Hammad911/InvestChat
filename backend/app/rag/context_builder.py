"""
Context builder — assembles structured context blocks from retrieved chunks
with source metadata for the LLM prompt.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.rag.retriever import RetrievedChunk


@dataclass
class ContextBlock:
    """A formatted context block with source attribution."""
    text: str
    source_label: str
    doc_id: str
    doc_type: str
    section_name: str
    page_number: int | None
    score: float


def build_context(
    chunks: list[RetrievedChunk],
    max_tokens: int = 4000,
    doc_name_map: dict[str, str] | None = None,
) -> tuple[str, list[dict]]:
    """
    Build structured context string and citation list from retrieved chunks.

    Returns:
        (context_string, citations_list)

    Context format:
        [Source: {doc_name} | {section} | Page {page}]
        {chunk_text}

    Citations list:
        [{"doc_id": ..., "doc_name": ..., "section": ..., "page": ..., "excerpt": ...}, ...]
    """
    doc_name_map = doc_name_map or {}

    blocks: list[ContextBlock] = []
    seen_texts: set[str] = set()

    for chunk in chunks:
        # Deduplicate overlapping chunks
        text_hash = chunk.text[:200]
        if text_hash in seen_texts:
            continue
        seen_texts.add(text_hash)

        doc_name = doc_name_map.get(chunk.doc_id, f"Document {chunk.doc_id[:8]}")
        page_str = f"Page {chunk.page_number}" if chunk.page_number else "N/A"
        source_label = f"{doc_name} | {chunk.section_name} | {page_str}"

        blocks.append(ContextBlock(
            text=chunk.text,
            source_label=source_label,
            doc_id=chunk.doc_id,
            doc_type=chunk.doc_type,
            section_name=chunk.section_name,
            page_number=chunk.page_number,
            score=chunk.score,
        ))

    # Trim to max tokens (approximate)
    context_parts = []
    citations = []
    current_tokens = 0

    for i, block in enumerate(blocks):
        block_tokens = len(block.text.split()) * 1.3
        if current_tokens + block_tokens > max_tokens:
            break

        context_parts.append(
            f"[Source {i + 1}: {block.source_label}]\n{block.text}"
        )
        citations.append({
            "citation_index": i + 1,
            "doc_id": block.doc_id,
            "doc_name": doc_name_map.get(block.doc_id, f"Document {block.doc_id[:8]}"),
            "doc_type": block.doc_type,
            "section": block.section_name,
            "page_number": block.page_number,
            "excerpt": block.text[:300],
            "relevance_score": round(block.score, 4),
        })
        current_tokens += block_tokens

    context_string = "\n\n---\n\n".join(context_parts)

    return context_string, citations


def format_citation_reference(index: int, doc_name: str, section: str, page: int | None) -> str:
    """Format an inline citation for LLM output."""
    page_str = f"Page {page}" if page else ""
    parts = [doc_name, section, page_str]
    return f"[Source {index}: {', '.join(p for p in parts if p)}]"
