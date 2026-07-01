"""
Resilient Gemini API client wrapper.

Key design decisions:
- Uses asyncio.get_event_loop().run_in_executor() to run the synchronous
  google-genai SDK in a thread pool — avoids blocking the FastAPI event loop.
- Retry decorator is defined at module level (not per-call) for efficiency.
- Timeout wraps a single attempt, not the whole retry chain.
- Streaming returns a sync iterator (intended for background thread use).
"""
from __future__ import annotations

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from fastapi import HTTPException
from tenacity import (
    RetryError,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# ── Thread pool for sync SDK calls ───────────────────────────────────────────
# The google-genai SDK is synchronous. We run it in a ThreadPoolExecutor so we
# don't block the FastAPI async event loop.
_EXECUTOR = ThreadPoolExecutor(max_workers=8, thread_name_prefix="gemini-worker")

# ── Retry predicate (module-level, not recreated per call) ───────────────────

def _is_retryable(exc: BaseException) -> bool:
    """Return True for transient Gemini errors worth retrying."""
    exc_type = type(exc).__name__
    msg = str(exc).lower()
    retryable_types = (
        "ResourceExhausted",
        "InternalServerError",
        "ServiceUnavailable",
        "DeadlineExceeded",
        "TooManyRequests",
    )
    if any(t in exc_type for t in retryable_types):
        return True
    if any(kw in msg for kw in ("quota", "rate limit", "503", "500", "429")):
        return True
    return False


# ── Module-level retry decorator (reused across all calls, not rebuilt) ───────

_RETRY = retry(
    retry=retry_if_exception(_is_retryable),
    stop=stop_after_attempt(3),
    # backoff: 1s, 2s, 4s (capped at 30s)
    wait=wait_exponential(multiplier=1, min=1, max=30),
    before_sleep=before_sleep_log(logging.getLogger(__name__), logging.WARNING),
    reraise=True,
)


# ── Sync low-level call (runs in executor thread) ────────────────────────────

def _sync_generate(
    prompt: str,
    model: str,
    temperature: float,
    response_mime_type: str,
    system_instruction: str | None,
    request_id: str | None,
) -> str:
    """
    Raw synchronous Gemini call. Decorated with retry at call sites.
    Runs inside a ThreadPoolExecutor to avoid blocking the event loop.
    """
    from google import genai
    from google.genai import types

    t0 = time.perf_counter()
    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    cfg: dict[str, Any] = {"temperature": temperature}
    if response_mime_type != "text/plain":
        cfg["response_mime_type"] = response_mime_type
    if system_instruction:
        cfg["system_instruction"] = system_instruction

    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(**cfg),
    )

    latency_ms = round((time.perf_counter() - t0) * 1000, 2)
    logger.info(
        "gemini_call_success",
        request_id=request_id,
        model=model,
        latency_ms=latency_ms,
    )
    return response.text


# Apply retry decorator at module level (efficient — not recreated per call)
_sync_generate_with_retry = _RETRY(_sync_generate)


# ── Public async API ─────────────────────────────────────────────────────────

async def generate_content(
    prompt: str,
    model: str | None = None,
    temperature: float = 0.2,
    response_mime_type: str = "text/plain",
    system_instruction: str | None = None,
    request_id: str | None = None,
) -> str:
    """
    Call Gemini generate_content from an async context.

    - Runs the sync SDK in a ThreadPoolExecutor (does not block event loop).
    - Per-attempt timeout: GEMINI_REQUEST_TIMEOUT applies to each individual
      attempt, not the whole retry chain.
    - Returns clean HTTPException(504) on timeout, 429 on exhausted retries.
    """
    model = model or settings.GEMINI_ANALYSIS_MODEL
    timeout = float(settings.GEMINI_REQUEST_TIMEOUT)
    loop = asyncio.get_event_loop()

    async def _one_attempt() -> str:
        """Single attempt wrapped with a per-attempt timeout."""
        try:
            return await asyncio.wait_for(
                loop.run_in_executor(
                    _EXECUTOR,
                    lambda: _sync_generate(
                        prompt, model, temperature,
                        response_mime_type, system_instruction, request_id,
                    ),
                ),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            logger.error(
                "gemini_timeout",
                request_id=request_id,
                model=model,
                timeout_seconds=timeout,
            )
            raise HTTPException(
                status_code=504,
                detail=f"Gemini API timed out after {timeout:.0f}s. Please try again.",
            )

    # Retry loop — each iteration applies the per-attempt timeout above
    last_exc: Exception = RuntimeError("no attempts made")
    for attempt in range(3):
        try:
            return await _one_attempt()
        except HTTPException:
            raise  # 504 timeout — don't retry, surface immediately
        except Exception as exc:
            last_exc = exc
            if not _is_retryable(exc):
                raise HTTPException(status_code=502, detail=f"Gemini API error: {exc}")
            if attempt < 2:
                wait_secs = min(2 ** attempt, 30)
                logger.warning(
                    "gemini_retry",
                    request_id=request_id,
                    attempt=attempt + 1,
                    wait_secs=wait_secs,
                    error=str(exc),
                )
                await asyncio.sleep(wait_secs)

    raise HTTPException(
        status_code=429,
        detail="Gemini API quota exceeded after 3 retries. Please wait and try again.",
    )


# ── Sync variant for Celery workers ──────────────────────────────────────────

def generate_content_sync(
    prompt: str,
    model: str | None = None,
    temperature: float = 0.2,
    response_mime_type: str = "text/plain",
    system_instruction: str | None = None,
) -> str:
    """
    Synchronous Gemini call with retry — for use in Celery tasks only.
    Do not call from FastAPI async routes (use generate_content instead).
    """
    model = model or settings.GEMINI_ANALYSIS_MODEL
    return _sync_generate_with_retry(
        prompt, model, temperature, response_mime_type, system_instruction, None
    )


# ── Streaming variant for SSE chat ───────────────────────────────────────────

def stream_content(
    prompt: str,
    model: str | None = None,
    temperature: float = 0.3,
    system_instruction: str | None = None,
):
    """
    Return a Gemini streaming response iterator.
    Intended to be called inside a ThreadPoolExecutor from the async chat route.
    No retry — streaming is stateful and cannot be naively retried.
    """
    from google import genai
    from google.genai import types

    model = model or settings.GEMINI_LLM_MODEL
    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    cfg: dict[str, Any] = {"temperature": temperature}
    if system_instruction:
        cfg["system_instruction"] = system_instruction

    return client.models.generate_content_stream(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(**cfg),
    )
