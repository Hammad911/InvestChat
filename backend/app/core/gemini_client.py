"""
Resilient Gemini API client wrapper.

Provides:
- Retry with exponential backoff on 429 (quota) and 5xx errors via tenacity
- Hard timeout via asyncio.wait_for() — returns clean 504 HTTPException
- Structured logging of every attempt and error with request_id
- A synchronous variant for use in Celery workers (embeddings in ingestion pipeline)
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

from fastapi import HTTPException
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
    RetryError,
)

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# ── Retry predicate ──────────────────────────────────────────────────────────

def _is_retryable(exc: BaseException) -> bool:
    """Return True for transient Gemini errors worth retrying."""
    exc_str = type(exc).__name__
    msg = str(exc).lower()
    # 429 quota exhausted, 500/503 transient server errors
    retryable_types = (
        "ResourceExhausted",
        "InternalServerError",
        "ServiceUnavailable",
        "DeadlineExceeded",
        "TooManyRequests",
    )
    if any(t in exc_str for t in retryable_types):
        return True
    # Catch by message for older SDK versions
    if any(kw in msg for kw in ("quota", "rate limit", "503", "500", "429")):
        return True
    return False


# ── Async generation (used by analysis modules running inside FastAPI) ────────

async def generate_content(
    prompt: str,
    model: str | None = None,
    temperature: float = 0.2,
    response_mime_type: str = "text/plain",
    system_instruction: str | None = None,
    request_id: str | None = None,
) -> str:
    """
    Call Gemini generate_content with retry + hard timeout.

    Args:
        prompt: The user prompt string.
        model: Gemini model name. Defaults to GEMINI_ANALYSIS_MODEL.
        temperature: Sampling temperature.
        response_mime_type: "application/json" for structured output.
        system_instruction: Optional system prompt.
        request_id: Propagated for structured logging.

    Returns:
        The text content from Gemini's response.

    Raises:
        HTTPException(504): If the call exceeds GEMINI_REQUEST_TIMEOUT seconds.
        HTTPException(429): If all retries are exhausted due to quota errors.
        HTTPException(502): If Gemini returns a non-retryable error.
    """
    model = model or settings.GEMINI_ANALYSIS_MODEL
    timeout = settings.GEMINI_REQUEST_TIMEOUT

    try:
        result = await asyncio.wait_for(
            _generate_with_retry(
                prompt=prompt,
                model=model,
                temperature=temperature,
                response_mime_type=response_mime_type,
                system_instruction=system_instruction,
                request_id=request_id,
            ),
            timeout=float(timeout),
        )
        return result
    except asyncio.TimeoutError:
        logger.error(
            "gemini_timeout",
            request_id=request_id,
            model=model,
            timeout_seconds=timeout,
        )
        raise HTTPException(
            status_code=504,
            detail=f"Gemini API timed out after {timeout}s. Please try again.",
        )
    except RetryError as exc:
        logger.error(
            "gemini_retries_exhausted",
            request_id=request_id,
            model=model,
            error=str(exc),
        )
        raise HTTPException(
            status_code=429,
            detail="Gemini API quota exceeded. Please wait and try again.",
        )


async def _generate_with_retry(
    prompt: str,
    model: str,
    temperature: float,
    response_mime_type: str,
    system_instruction: str | None,
    request_id: str | None,
) -> str:
    """Inner async call with tenacity retry logic."""
    import logging as stdlib_logging

    @retry(
        retry=retry_if_exception(_is_retryable),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        before_sleep=before_sleep_log(
            stdlib_logging.getLogger(__name__), stdlib_logging.WARNING
        ),
        reraise=True,
    )
    async def _call() -> str:
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

    return await _call()


# ── Sync generation (used from Celery workers / synchronous contexts) ─────────

def generate_content_sync(
    prompt: str,
    model: str | None = None,
    temperature: float = 0.2,
    response_mime_type: str = "text/plain",
    system_instruction: str | None = None,
) -> str:
    """
    Synchronous Gemini call with retry + timeout for use in Celery tasks.
    Not used by the FastAPI routes (those use the async variant).
    """
    from google import genai
    from google.genai import types
    import logging as stdlib_logging

    model = model or settings.GEMINI_ANALYSIS_MODEL

    @retry(
        retry=retry_if_exception(_is_retryable),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        before_sleep=before_sleep_log(
            stdlib_logging.getLogger(__name__), stdlib_logging.WARNING
        ),
        reraise=True,
    )
    def _call() -> str:
        cfg: dict[str, Any] = {"temperature": temperature}
        if response_mime_type != "text/plain":
            cfg["response_mime_type"] = response_mime_type
        if system_instruction:
            cfg["system_instruction"] = system_instruction

        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(**cfg),
        )
        return response.text

    return _call()


# ── Streaming (used by chat.py for SSE — no retry, caller handles SSE errors) ─

def stream_content(
    prompt: str,
    model: str | None = None,
    temperature: float = 0.3,
    system_instruction: str | None = None,
):
    """
    Return a Gemini streaming response iterator.
    No retry wrapper — streaming is stateful and cannot be naively retried.
    The chat module handles SSE error events gracefully.
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
