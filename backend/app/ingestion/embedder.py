"""
Embedding and vector storage via Gemini API (text-embedding-004) + Qdrant.
Handles both dense embeddings and BM25 sparse vectors.
"""
from __future__ import annotations

import hashlib
import math
import re
from collections import Counter

from google import genai
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    NamedSparseVector,
    NamedVector,
    PointStruct,
    SparseVector,
    VectorParams,
    SparseVectorParams,
    Modifier,
)

from app.core.config import settings
from app.core.logging import get_logger
from app.ingestion.chunker import Chunk

logger = get_logger(__name__)

EMBED_DIM = 3072  # gemini-embedding-2 output dimensions
BATCH_SIZE = 32


def get_qdrant_client() -> QdrantClient:
    return QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)


def ensure_collection() -> None:
    """Create the Qdrant collection if it doesn't exist."""
    client = get_qdrant_client()
    collections = [c.name for c in client.get_collections().collections]

    if settings.QDRANT_COLLECTION not in collections:
        client.create_collection(
            collection_name=settings.QDRANT_COLLECTION,
            vectors_config={
                "dense": VectorParams(size=EMBED_DIM, distance=Distance.COSINE),
            },
            sparse_vectors_config={
                "bm25": SparseVectorParams(modifier=Modifier.IDF),
            },
        )
        logger.info("qdrant_collection_created", name=settings.QDRANT_COLLECTION)
    else:
        logger.info("qdrant_collection_exists", name=settings.QDRANT_COLLECTION)


def _get_dense_embeddings(texts: list[str]) -> list[list[float]]:
    """Get dense embeddings via direct REST call to the Gemini API.
    
    Uses httpx directly to avoid google-genai SDK version issues.
    Includes retry with exponential backoff for 429 rate limit errors.
    """
    import httpx
    import time

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.GEMINI_EMBED_MODEL}:batchEmbedContents"
        f"?key={settings.GEMINI_API_KEY}"
    )

    embeddings: list[list[float]] = []

    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        payload = {
            "requests": [
                {
                    "model": f"models/{settings.GEMINI_EMBED_MODEL}",
                    "content": {"parts": [{"text": t}]},
                }
                for t in batch
            ]
        }

        # Retry with exponential backoff on 429
        max_retries = 5
        for attempt in range(max_retries):
            response = httpx.post(url, json=payload, timeout=60.0)
            if response.status_code == 429:
                wait = min(2 ** attempt * 2, 60)  # 2s, 4s, 8s, 16s, 32s
                logger.warning(
                    "rate_limited",
                    batch_index=i,
                    attempt=attempt + 1,
                    wait_seconds=wait,
                )
                time.sleep(wait)
                continue
            response.raise_for_status()
            break
        else:
            # All retries exhausted
            response.raise_for_status()

        data = response.json()
        for embedding_obj in data.get("embeddings", []):
            embeddings.append(embedding_obj["values"])
        logger.debug("embeddings_batch", batch_index=i, batch_size=len(batch))

        # Throttle between batches to stay within rate limits
        if i + BATCH_SIZE < len(texts):
            time.sleep(1.5)

    return embeddings



def _tokenize(text: str) -> list[str]:
    """Simple whitespace + punctuation tokenizer for BM25."""
    return re.findall(r"\b\w+\b", text.lower())


def _build_sparse_vector(text: str, vocab: dict[str, int] | None = None) -> SparseVector:
    """Build a sparse BM25 vector from text."""
    tokens = _tokenize(text)
    if not tokens:
        return SparseVector(indices=[], values=[])

    term_freq = Counter(tokens)
    indices = []
    values = []

    for token, freq in term_freq.items():
        # Use a hash to map tokens to indices (deterministic)
        idx = int(hashlib.md5(token.encode()).hexdigest()[:8], 16) % (2**31)
        # TF component: log(1 + tf)
        tf = math.log(1 + freq)
        indices.append(idx)
        values.append(tf)

    return SparseVector(indices=indices, values=values)


def embed_and_store(chunks: list[Chunk]) -> int:
    """
    Embed chunks and store in Qdrant with both dense and sparse vectors.
    Returns the number of points stored.
    """
    if not chunks:
        return 0

    # Filter to only child chunks (parents stored for context retrieval only)
    embeddable = [c for c in chunks if c.parent_chunk_id is not None or c.is_table]
    if not embeddable:
        # If no children, embed all chunks
        embeddable = chunks

    logger.info("embedding_start", total_chunks=len(chunks), embeddable=len(embeddable))

    texts = [c.text for c in embeddable]
    dense_vectors = _get_dense_embeddings(texts)

    client = get_qdrant_client()
    points = []

    for i, chunk in enumerate(embeddable):
        sparse = _build_sparse_vector(chunk.text)
        point = PointStruct(
            id=chunk.chunk_id,
            vector={
                "dense": dense_vectors[i],
            },
            payload={
                "project_id": chunk.project_id,
                "doc_id": chunk.doc_id,
                "doc_type": chunk.doc_type,
                "section_name": chunk.section_name,
                "page_number": chunk.page_number,
                "chunk_index": chunk.chunk_index,
                "is_table": chunk.is_table,
                "parent_chunk_id": chunk.parent_chunk_id,
                "fiscal_year": chunk.fiscal_year,
                "text": chunk.text,
            },
        )
        points.append(point)

    # Upsert in batches
    for i in range(0, len(points), BATCH_SIZE):
        batch = points[i : i + BATCH_SIZE]
        client.upsert(collection_name=settings.QDRANT_COLLECTION, points=batch)
        logger.debug("qdrant_upsert_batch", batch_index=i, batch_size=len(batch))

    logger.info("embedding_complete", points_stored=len(points))
    return len(points)


def delete_document_vectors(doc_id: str) -> None:
    """Delete all vectors for a specific document."""
    from qdrant_client.models import Filter, FieldCondition, MatchValue

    client = get_qdrant_client()
    client.delete(
        collection_name=settings.QDRANT_COLLECTION,
        points_selector=Filter(
            must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
        ),
    )
    logger.info("vectors_deleted", doc_id=doc_id)
