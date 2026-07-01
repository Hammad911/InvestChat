"""
Growth opportunities analysis module.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone

from app.core.config import settings
from app.core.logging import get_logger
from app.core.semantic_cache import SemanticCache, record_latency
from app.rag.context_builder import build_context
from app.rag.reranker import rerank
from app.rag.retriever import expand_parent_context, hybrid_search

logger = get_logger(__name__)

_cache = SemanticCache(namespace="growth")

GROWTH_PROMPT = """You are a senior investment analyst. Analyze the provided documents and identify growth opportunities.

For each opportunity, provide:
1. opportunity_title: Short descriptive title
2. supporting_evidence: Key evidence from the documents
3. confidence_score: A confidence score from 0.0 to 1.0
4. source_citations: Reference the source numbers provided in the context

CONTEXT:
{context}

Respond ONLY with a valid JSON object:
{{
  "opportunities": [
    {{
      "opportunity_title": "Title",
      "supporting_evidence": ["Evidence 1", "Evidence 2"],
      "confidence_score": 0.8,
      "source_citations": [1, 3]
    }}
  ],
  "market_outlook": "Brief market outlook summary",
  "summary": "Overall growth assessment"
}}
"""


async def analyze_growth(
    project_id: str,
    doc_name_map: dict[str, str] | None = None,
    request_id: str | None = None,
) -> dict:
    """Run growth opportunity analysis. Checks semantic cache before calling Gemini."""
    logger.info("growth_analysis_start", project_id=project_id, request_id=request_id)

    # ── Cache lookup ─────────────────────────────────────────────────────────
    cache_key = f"growth:{project_id}"
    t_cache = time.perf_counter()
    cached = _cache.get(cache_key)
    cache_latency_ms = round((time.perf_counter() - t_cache) * 1000, 2)

    if cached is not None:
        logger.info(
            "growth_analysis_cache_hit",
            project_id=project_id,
            request_id=request_id,
            cache_latency_ms=cache_latency_ms,
        )
        return cached

    # ── Retrieval ────────────────────────────────────────────────────────────
    t_retrieval = time.perf_counter()
    chunks = hybrid_search(
        query="growth opportunities market expansion competitive advantage innovation strategy",
        project_id=project_id,
        top_k=20,
    )
    chunks = expand_parent_context(chunks)
    retrieval_latency_ms = round((time.perf_counter() - t_retrieval) * 1000, 2)
    record_latency("retrieval", retrieval_latency_ms)

    t_rerank = time.perf_counter()
    chunks = rerank("growth opportunities and competitive advantages", chunks, top_n=8)
    rerank_latency_ms = round((time.perf_counter() - t_rerank) * 1000, 2)
    top_rerank_score = chunks[0].score if chunks else 0.0

    logger.info(
        "growth_analysis_retrieval_complete",
        request_id=request_id,
        stage="retrieval+rerank",
        latency_ms=retrieval_latency_ms + rerank_latency_ms,
        cache_hit=False,
        num_chunks_retrieved=len(chunks),
        rerank_top_score=round(top_rerank_score, 4),
    )

    context_str, citations = build_context(chunks, max_tokens=3500, doc_name_map=doc_name_map)

    if not context_str:
        return {
            "opportunities": [],
            "market_outlook": "Insufficient data",
            "summary": "No growth-related content found.",
            "citations": [],
        }

    # ── Gemini call ──────────────────────────────────────────────────────────
    from app.core.gemini_client import generate_content

    prompt = GROWTH_PROMPT.format(context=context_str)
    t_llm = time.perf_counter()
    raw_output = await generate_content(
        prompt=prompt,
        model=settings.GEMINI_ANALYSIS_MODEL,
        temperature=0.2,
        response_mime_type="application/json",
        request_id=request_id,
    )
    llm_latency_ms = round((time.perf_counter() - t_llm) * 1000, 2)
    record_latency("generation", llm_latency_ms)

    logger.info(
        "growth_analysis_llm_complete",
        request_id=request_id,
        stage="gemini_generation",
        latency_ms=llm_latency_ms,
        cache_hit=False,
        num_chunks_retrieved=len(chunks),
        rerank_top_score=round(top_rerank_score, 4),
    )

    try:
        json_start = raw_output.find("{")
        json_end = raw_output.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            result = json.loads(raw_output[json_start:json_end])
        else:
            result = {"opportunities": [], "summary": raw_output}
    except json.JSONDecodeError:
        result = {"opportunities": [], "summary": raw_output}

    result["citations"] = citations
    result["model_used"] = settings.GEMINI_ANALYSIS_MODEL
    result["analyzed_at"] = datetime.now(timezone.utc).isoformat()

    _cache.set(cache_key, result)

    logger.info(
        "growth_analysis_complete",
        project_id=project_id,
        request_id=request_id,
        opportunity_count=len(result.get("opportunities", [])),
    )
    return result
