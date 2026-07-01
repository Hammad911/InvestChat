"""
Semantic cache backed by Redis.

Flow:
  1. Embed incoming query via Gemini text-embedding
  2. Scan Redis for stored (query_vector, response) pairs
  3. If cosine similarity ≥ SEMANTIC_CACHE_THRESHOLD → return cached response
  4. Otherwise return None; caller stores response via .set()

Only used for deterministic analysis endpoints (risks, growth, financials,
summary). NOT used for streaming SSE chat responses.
"""
from __future__ import annotations

import json
import time
from typing import Any

import numpy as np
import redis as redis_lib

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Redis key prefix and TTL
_CACHE_PREFIX = "semantic_cache:"
_CACHE_TTL_SECONDS = 60 * 60 * 24  # 24 hours


def _get_redis() -> redis_lib.Redis:
    """Return a Redis client pointed at the semantic cache DB."""
    return redis_lib.from_url(
        settings.REDIS_URL.rsplit("/", 1)[0] + f"/{settings.SEMANTIC_CACHE_REDIS_DB}",
        decode_responses=False,
    )


def _embed_query(text: str) -> list[float]:
    """Embed a query string using Gemini text-embedding."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    result = client.models.embed_content(
        model=settings.GEMINI_EMBED_MODEL,
        contents=[text],
        config=types.EmbedContentConfig(output_dimensionality=768),
    )
    return list(result.embeddings[0].values)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    norm_a = np.linalg.norm(va)
    norm_b = np.linalg.norm(vb)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(va, vb) / (norm_a * norm_b))


class SemanticCache:
    """
    Semantic similarity cache for expensive, deterministic Gemini calls.

    Each entry is stored in Redis as a JSON blob under a unique key.
    On lookup, all existing entry vectors are compared against the query
    vector — O(n) over cached entries, which is fine for dozens-to-hundreds
    of analysis results per deployment.
    """

    def __init__(self, namespace: str) -> None:
        """
        Args:
            namespace: Logical grouping for this cache (e.g. "risks", "growth").
                       Used as part of the Redis key to avoid cross-namespace hits.
        """
        self._ns = namespace
        self._threshold = settings.SEMANTIC_CACHE_THRESHOLD

    def _scan_keys(self, r: redis_lib.Redis) -> list[bytes]:
        """Return all Redis keys belonging to this namespace."""
        pattern = f"{_CACHE_PREFIX}{self._ns}:*"
        return list(r.scan_iter(match=pattern))

    def get(self, cache_key: str) -> Any | None:
        """
        Look up a cached response.

        Args:
            cache_key: A human-readable identifier, e.g. "{analysis_type}:{project_id}".
                       Embedded via Gemini, then compared against stored vectors.

        Returns:
            The cached response dict, or None on cache miss.
        """
        t0 = time.perf_counter()
        try:
            r = _get_redis()
            query_vec = _embed_query(cache_key)
            keys = self._scan_keys(r)

            best_score = 0.0
            best_payload = None

            for key in keys:
                raw = r.get(key)
                if raw is None:
                    continue
                try:
                    entry = json.loads(raw)
                except (json.JSONDecodeError, ValueError):
                    continue

                stored_vec = entry.get("query_vec")
                if not stored_vec:
                    continue

                score = _cosine_similarity(query_vec, stored_vec)
                if score > best_score:
                    best_score = score
                    best_payload = entry.get("response")

            latency_ms = round((time.perf_counter() - t0) * 1000, 2)

            if best_score >= self._threshold and best_payload is not None:
                logger.info(
                    "semantic_cache_hit",
                    namespace=self._ns,
                    cache_key=cache_key,
                    similarity=round(best_score, 4),
                    latency_ms=latency_ms,
                )
                return best_payload

            logger.info(
                "semantic_cache_miss",
                namespace=self._ns,
                cache_key=cache_key,
                best_similarity=round(best_score, 4),
                num_entries_checked=len(keys),
                latency_ms=latency_ms,
            )
            return None

        except Exception as exc:
            logger.warning(
                "semantic_cache_get_error",
                namespace=self._ns,
                cache_key=cache_key,
                error=str(exc),
            )
            return None

    def set(self, cache_key: str, response: Any) -> None:
        """
        Store a response in the cache.

        Args:
            cache_key: Same key passed to .get().
            response:  The dict/value to cache.
        """
        try:
            r = _get_redis()
            query_vec = _embed_query(cache_key)

            # Use a hash of the key + timestamp as the Redis key suffix
            import hashlib
            suffix = hashlib.sha256(f"{cache_key}:{time.time()}".encode()).hexdigest()[:16]
            redis_key = f"{_CACHE_PREFIX}{self._ns}:{suffix}"

            payload = json.dumps(
                {
                    "query_vec": query_vec,
                    "response": response,
                    "cache_key": cache_key,
                    "created_at": time.time(),
                }
            )
            r.setex(redis_key, _CACHE_TTL_SECONDS, payload)

            logger.info(
                "semantic_cache_stored",
                namespace=self._ns,
                cache_key=cache_key,
                redis_key=redis_key,
            )
        except Exception as exc:
            # Cache failures must never break the actual response
            logger.warning(
                "semantic_cache_set_error",
                namespace=self._ns,
                cache_key=cache_key,
                error=str(exc),
            )

    # ── Metrics helpers (used by /system/metrics) ────────────────────────────

    def record_hit(self) -> None:
        """Increment hit counter in Redis for the metrics endpoint."""
        _increment_metric("cache_hit", self._ns)

    def record_miss(self) -> None:
        """Increment miss counter in Redis for the metrics endpoint."""
        _increment_metric("cache_miss", self._ns)


def _increment_metric(metric: str, namespace: str) -> None:
    """Increment a rolling 1-hour counter in Redis DB 0 (shared with Celery)."""
    try:
        r = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)
        # Bucket by minute so we can sum the last 60 buckets
        bucket = int(time.time() // 60)
        key = f"metrics:{metric}:{namespace}:{bucket}"
        pipe = r.pipeline()
        pipe.incr(key)
        pipe.expire(key, 3700)  # keep slightly more than 1 hr
        pipe.execute()
    except Exception:
        pass  # metrics are best-effort


def record_latency(stage: str, latency_ms: float) -> None:
    """Push a latency sample to a Redis list for rolling average calculation."""
    try:
        r = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)
        key = f"metrics:latency:{stage}"
        pipe = r.pipeline()
        pipe.lpush(key, latency_ms)
        pipe.ltrim(key, 0, 999)   # keep last 1000 samples
        pipe.execute()
    except Exception:
        pass  # metrics are best-effort
