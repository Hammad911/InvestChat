"""
Cross-encoder reranker using sentence-transformers (local, no API).
Model: cross-encoder/ms-marco-MiniLM-L-6-v2
"""
from __future__ import annotations

from functools import lru_cache

from app.core.logging import get_logger
from app.rag.retriever import RetrievedChunk

logger = get_logger(__name__)


@lru_cache(maxsize=1)
def _load_cross_encoder():
    """Load the cross-encoder model (cached — loaded once, reused)."""
    from sentence_transformers import CrossEncoder

    logger.info("loading_cross_encoder", model="cross-encoder/ms-marco-MiniLM-L-6-v2")
    model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    logger.info("cross_encoder_loaded")
    return model


def rerank(
    query: str,
    chunks: list[RetrievedChunk],
    top_n: int = 5,
) -> list[RetrievedChunk]:
    """
    Re-rank retrieved chunks using a cross-encoder model.
    Returns the top_n most relevant chunks.
    """
    if not chunks:
        return []

    if len(chunks) <= top_n:
        return chunks

    model = _load_cross_encoder()

    # Build query-document pairs for scoring
    pairs = [(query, chunk.text) for chunk in chunks]
    scores = model.predict(pairs)

    # Attach reranker scores and sort
    scored_chunks = list(zip(chunks, scores))
    scored_chunks.sort(key=lambda x: x[1], reverse=True)

    results = []
    for chunk, score in scored_chunks[:top_n]:
        chunk.score = float(score)
        chunk.metadata["reranker_score"] = float(score)
        results.append(chunk)

    logger.info(
        "rerank_complete",
        input_chunks=len(chunks),
        output_chunks=len(results),
        top_score=results[0].score if results else 0,
    )
    return results
