"""
Embedding and vector storage via local sentence-transformers + Qdrant.
Handles both dense embeddings and BM25 sparse vectors.
"""
from __future__ import annotations

import hashlib
import math
import re
from collections import Counter

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

EMBED_DIM = 768  # all-mpnet-base-v2 output dimensions
BATCH_SIZE = 32
# Gemini embedding replaces local sentence transformers
_EMBED_MODEL = "gemini-used-instead"

def _get_model():
    # Deprecated. Handled directly via Gemini now.
    pass


def get_qdrant_client() -> QdrantClient:
    if settings.QDRANT_URL and settings.QDRANT_API_KEY:
        return QdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY,
        )
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
    """Get dense embeddings using Gemini text-embedding-004.
    
    Bypasses local sentence-transformers to avoid memory spikes and OOM kills.
    """
    from google import genai
    
    from google.genai import types
    
    if not texts:
        return []
        
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    
    # Gemini handles batching natively, but we can send the whole list
    # The API might have limits on batch size, so we'll chunk the list just in case
    embeddings = []
    
    # Process in batches of 100 to respect Gemini API limits
    batch_size = 100
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        result = client.models.embed_content(
            model=settings.GEMINI_EMBED_MODEL,
            contents=batch,
            config=types.EmbedContentConfig(output_dimensionality=768)
        )
        for e in result.embeddings:
            embeddings.append(e.values)
            
    logger.info("embeddings_complete", count=len(texts))
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
