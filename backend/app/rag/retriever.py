"""
Multi-strategy retriever with dense, sparse, and hybrid search.
Supports parent-child context expansion.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import httpx
from qdrant_client import QdrantClient
from qdrant_client.models import (
    FieldCondition,
    Filter,
    MatchAny,
    MatchValue,
    NamedSparseVector,
    SearchParams,
    SearchRequest,
    SparseVector,
)

from app.core.config import settings
from app.core.logging import get_logger
from app.ingestion.embedder import _build_sparse_vector, get_qdrant_client

logger = get_logger(__name__)


@dataclass
class RetrievedChunk:
    """A retrieved chunk with relevance score."""
    chunk_id: str
    text: str
    score: float
    doc_id: str
    doc_type: str
    section_name: str
    page_number: int | None
    is_table: bool
    parent_chunk_id: str | None
    fiscal_year: str | None
    parent_text: str | None = None  # Expanded parent context
    metadata: dict = field(default_factory=dict)


def _get_query_embedding(query: str) -> list[float]:
    """Get dense embedding for a query via Gemini REST API."""
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.GEMINI_EMBED_MODEL}:embedContent"
        f"?key={settings.GEMINI_API_KEY}"
    )
    payload = {
        "model": f"models/{settings.GEMINI_EMBED_MODEL}",
        "content": {"parts": [{"text": query}]},
    }
    response = httpx.post(url, json=payload, timeout=30.0)
    response.raise_for_status()
    return response.json()["embedding"]["values"]


def _build_filter(
    project_id: str,
    section_filters: list[str] | None = None,
    doc_type_filters: list[str] | None = None,
) -> Filter:
    """Build Qdrant filter from query routing metadata."""
    must = [FieldCondition(key="project_id", match=MatchValue(value=project_id))]

    if section_filters:
        must.append(
            FieldCondition(key="section_name", match=MatchAny(any=section_filters))
        )
    if doc_type_filters:
        must.append(
            FieldCondition(key="doc_type", match=MatchAny(any=doc_type_filters))
        )

    return Filter(must=must)


def _points_to_chunks(points: list) -> list[RetrievedChunk]:
    """Convert Qdrant search results to RetrievedChunk objects."""
    chunks = []
    for point in points:
        payload = point.payload or {}
        chunks.append(RetrievedChunk(
            chunk_id=str(point.id),
            text=payload.get("text", ""),
            score=point.score,
            doc_id=payload.get("doc_id", ""),
            doc_type=payload.get("doc_type", ""),
            section_name=payload.get("section_name", ""),
            page_number=payload.get("page_number"),
            is_table=payload.get("is_table", False),
            parent_chunk_id=payload.get("parent_chunk_id"),
            fiscal_year=payload.get("fiscal_year"),
        ))
    return chunks


def dense_search(
    query: str,
    project_id: str,
    top_k: int = 20,
    section_filters: list[str] | None = None,
    doc_type_filters: list[str] | None = None,
) -> list[RetrievedChunk]:
    """Dense vector similarity search via Qdrant."""
    client = get_qdrant_client()
    query_vector = _get_query_embedding(query)
    qfilter = _build_filter(project_id, section_filters, doc_type_filters)

    results = client.search(
        collection_name=settings.QDRANT_COLLECTION,
        query_vector=("dense", query_vector),
        query_filter=qfilter,
        limit=top_k,
        with_payload=True,
    )
    return _points_to_chunks(results)


def sparse_search(
    query: str,
    project_id: str,
    top_k: int = 20,
    section_filters: list[str] | None = None,
    doc_type_filters: list[str] | None = None,
) -> list[RetrievedChunk]:
    """BM25 sparse vector search via Qdrant."""
    client = get_qdrant_client()
    sparse_vector = _build_sparse_vector(query)
    qfilter = _build_filter(project_id, section_filters, doc_type_filters)

    results = client.search(
        collection_name=settings.QDRANT_COLLECTION,
        query_vector=NamedSparseVector(
            name="bm25",
            vector=sparse_vector,
        ),
        query_filter=qfilter,
        limit=top_k,
        with_payload=True,
    )
    return _points_to_chunks(results)


def hybrid_search(
    query: str,
    project_id: str,
    top_k: int = 10,
    dense_weight: float = 0.7,
    sparse_weight: float = 0.3,
    section_filters: list[str] | None = None,
    doc_type_filters: list[str] | None = None,
) -> list[RetrievedChunk]:
    """
    Hybrid search using Reciprocal Rank Fusion (RRF) to merge
    dense and sparse results.
    """
    dense_results = dense_search(
        query, project_id, top_k=top_k * 2,
        section_filters=section_filters, doc_type_filters=doc_type_filters,
    )
    sparse_results = sparse_search(
        query, project_id, top_k=top_k * 2,
        section_filters=section_filters, doc_type_filters=doc_type_filters,
    )

    # RRF fusion
    rrf_scores: dict[str, float] = {}
    chunk_map: dict[str, RetrievedChunk] = {}
    k = 60  # RRF constant

    for rank, chunk in enumerate(dense_results):
        rrf_scores[chunk.chunk_id] = rrf_scores.get(chunk.chunk_id, 0) + \
            dense_weight * (1.0 / (k + rank + 1))
        chunk_map[chunk.chunk_id] = chunk

    for rank, chunk in enumerate(sparse_results):
        rrf_scores[chunk.chunk_id] = rrf_scores.get(chunk.chunk_id, 0) + \
            sparse_weight * (1.0 / (k + rank + 1))
        if chunk.chunk_id not in chunk_map:
            chunk_map[chunk.chunk_id] = chunk

    # Sort by RRF score
    sorted_ids = sorted(rrf_scores, key=rrf_scores.get, reverse=True)[:top_k]

    results = []
    for cid in sorted_ids:
        chunk = chunk_map[cid]
        chunk.score = rrf_scores[cid]
        results.append(chunk)

    logger.info(
        "hybrid_search_complete",
        query_len=len(query),
        dense_results=len(dense_results),
        sparse_results=len(sparse_results),
        fused_results=len(results),
    )
    return results


def expand_parent_context(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    """
    Fetch parent chunks to provide fuller context around retrieved children.
    """
    client = get_qdrant_client()
    parent_ids = {
        c.parent_chunk_id for c in chunks
        if c.parent_chunk_id is not None
    }

    if not parent_ids:
        return chunks

    # Fetch parent chunks from Qdrant
    parent_points = client.retrieve(
        collection_name=settings.QDRANT_COLLECTION,
        ids=list(parent_ids),
        with_payload=True,
    )
    parent_map = {
        str(p.id): p.payload.get("text", "") for p in parent_points
    }

    # Attach parent text to children
    for chunk in chunks:
        if chunk.parent_chunk_id and chunk.parent_chunk_id in parent_map:
            chunk.parent_text = parent_map[chunk.parent_chunk_id]

    return chunks
