"""
Analysis result cache backed by Redis.

Design:
  - Cache key is a deterministic string (analysis_type:project_id).
    These keys are NOT fuzzy queries — no semantic similarity is needed.
  - Lookup is a single Redis GET: O(1), no API call, sub-millisecond.
  - Value stored as MessagePack (compact binary) with a TTL.
  - Cache is invalidated when a new document is ingested for the project.

Why NOT semantic similarity for this use case:
  The analysis modules always produce the same cache key for the same project
  (e.g. "risks:abc123"). Using cosine similarity + Gemini embedding on a
  deterministic key makes cache lookup SLOWER than just calling Gemini directly.
  Semantic similarity caches are appropriate for free-text user queries (chat),
  not for structured analysis jobs with fixed keys.

TTL strategy:
  Default 24 hours. Should be invalidated on document upload via
  SemanticCache.invalidate(project_id) in the ingestion pipeline.
"""
from __future__ import annotations

import json
import time
from typing import Any

import redis as redis_lib

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_CACHE_PREFIX = "analysis_cache:"
_CACHE_TTL_SECONDS = 60 * 60 * 24  # 24 hours
_METRICS_PREFIX = "metrics:"


def _get_redis() -> redis_lib.Redis:
    """Return a Redis client on the semantic cache DB index."""
    base_url = settings.REDIS_URL.rsplit("/", 1)[0]
    return redis_lib.from_url(
        f"{base_url}/{settings.SEMANTIC_CACHE_REDIS_DB}",
        decode_responses=False,
        socket_connect_timeout=2,
        socket_timeout=2,
    )


class SemanticCache:
    """
    Fast deterministic cache for expensive analysis results.

    Lookup is a single Redis GET — O(1), zero API calls.
    Entries expire after 24h and are also invalidated on document upload.

    Usage:
        cache = SemanticCache(namespace="risks")
        result = cache.get("risks:project-uuid")
        if result is None:
            result = run_expensive_analysis(...)
            cache.set("risks:project-uuid", result)
    """

    def __init__(self, namespace: str) -> None:
        self._ns = namespace
        self._r: redis_lib.Redis | None = None

    def _redis(self) -> redis_lib.Redis:
        if self._r is None:
            self._r = _get_redis()
        return self._r

    def _redis_key(self, cache_key: str) -> str:
        import hashlib
        h = hashlib.sha256(f"{self._ns}:{cache_key}".encode()).hexdigest()
        return f"{_CACHE_PREFIX}{self._ns}:{h}"

    def get(self, cache_key: str) -> Any | None:
        """
        O(1) cache lookup. Returns cached result or None.
        Never makes a Gemini API call.
        """
        t0 = time.perf_counter()
        try:
            raw = self._redis().get(self._redis_key(cache_key))
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)

            if raw is not None:
                result = json.loads(raw)
                logger.info(
                    "cache_hit",
                    namespace=self._ns,
                    cache_key=cache_key,
                    latency_ms=latency_ms,
                )
                self._record_metric("hit")
                return result

            logger.info(
                "cache_miss",
                namespace=self._ns,
                cache_key=cache_key,
                latency_ms=latency_ms,
            )
            self._record_metric("miss")
            return None

        except Exception as exc:
            # Cache must never break the actual request
            logger.warning("cache_get_error", namespace=self._ns, error=str(exc))
            return None

    def set(self, cache_key: str, response: Any) -> None:
        """Store result. Compressed JSON with TTL. Never raises."""
        try:
            self._redis().setex(
                self._redis_key(cache_key),
                _CACHE_TTL_SECONDS,
                json.dumps(response, default=str),
            )
            logger.info("cache_stored", namespace=self._ns, cache_key=cache_key)
        except Exception as exc:
            logger.warning("cache_set_error", namespace=self._ns, error=str(exc))

    def invalidate(self, cache_key: str) -> None:
        """
        Explicitly invalidate a cached result.
        Call this from the ingestion pipeline after a new document is uploaded,
        so analysis results are regenerated with fresh data.
        """
        try:
            self._redis().delete(self._redis_key(cache_key))
            logger.info("cache_invalidated", namespace=self._ns, cache_key=cache_key)
        except Exception as exc:
            logger.warning("cache_invalidate_error", namespace=self._ns, error=str(exc))

    def _record_metric(self, event: str) -> None:
        """Increment per-minute hit/miss counters in Redis DB 0 for /system/metrics."""
        try:
            r0 = redis_lib.from_url(settings.REDIS_URL, decode_responses=True,
                                    socket_timeout=1)
            bucket = int(time.time() // 60)
            key = f"{_METRICS_PREFIX}cache_{event}:{self._ns}:{bucket}"
            pipe = r0.pipeline()
            pipe.incr(key)
            pipe.expire(key, 3700)
            pipe.execute()
        except Exception:
            pass  # metrics are best-effort


def record_latency(stage: str, latency_ms: float) -> None:
    """
    Push a latency sample to Redis for rolling average in /system/metrics.
    Non-blocking best-effort: always succeeds from the caller's perspective.
    """
    try:
        r = redis_lib.from_url(settings.REDIS_URL, decode_responses=True,
                                socket_timeout=1)
        key = f"{_METRICS_PREFIX}latency:{stage}"
        pipe = r.pipeline()
        pipe.lpush(key, latency_ms)
        pipe.ltrim(key, 0, 999)   # keep last 1000 samples (~16min at 1 req/s)
        pipe.execute()
    except Exception:
        pass


def invalidate_project_cache(project_id: str) -> None:
    """
    Invalidate all analysis cache entries for a project.
    Call from the ingestion pipeline after document upload completes,
    so the next analysis request re-runs with fresh document data.
    """
    namespaces = ["risks", "growth", "financials", "summary"]
    for ns in namespaces:
        cache = SemanticCache(namespace=ns)
        cache.invalidate(f"{ns}:{project_id}")
