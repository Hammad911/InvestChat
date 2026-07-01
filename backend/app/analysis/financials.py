"""
Financial metrics extraction module.
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

_cache = SemanticCache(namespace="financials")

FINANCIALS_PROMPT = """You are a financial analyst. Extract key financial metrics from the provided documents.

Extract the following metrics if available:
- Revenue (with YoY growth %)
- Gross Margin (%)
- EBITDA
- Net Income
- Operating Cash Flow
- Burn Rate (if applicable)
- Cash Runway (if applicable)
- CAC (Customer Acquisition Cost)
- LTV (Lifetime Value)
- Total Addressable Market (TAM)

CONTEXT:
{context}

Respond ONLY with a valid JSON object:
{{
  "metrics": [
    {{
      "metric_name": "Revenue",
      "value": "$X.XM",
      "period": "FY2023",
      "yoy_change": "+15%",
      "source_citations": [1]
    }}
  ],
  "financial_health": "Strong|Moderate|Weak",
  "key_observations": ["Observation 1", "Observation 2"],
  "summary": "Brief financial overview"
}}
"""


async def analyze_financials(
    project_id: str,
    doc_name_map: dict[str, str] | None = None,
    request_id: str | None = None,
) -> dict:
    """Run financial metrics extraction. Checks semantic cache before calling Gemini."""
    logger.info("financial_analysis_start", project_id=project_id, request_id=request_id)

    # ── Cache lookup ─────────────────────────────────────────────────────────
    cache_key = f"financials:{project_id}"
    t_cache = time.perf_counter()
    cached = _cache.get(cache_key)
    cache_latency_ms = round((time.perf_counter() - t_cache) * 1000, 2)

    if cached is not None:
        logger.info(
            "financial_analysis_cache_hit",
            project_id=project_id,
            request_id=request_id,
            cache_latency_ms=cache_latency_ms,
        )
        return cached

    # ── Retrieval ────────────────────────────────────────────────────────────
    t_retrieval = time.perf_counter()
    chunks = hybrid_search(
        query="revenue profit margin EBITDA net income cash flow financial results earnings",
        project_id=project_id,
        top_k=20,
    )
    chunks = expand_parent_context(chunks)
    retrieval_latency_ms = round((time.perf_counter() - t_retrieval) * 1000, 2)
    record_latency("retrieval", retrieval_latency_ms)

    t_rerank = time.perf_counter()
    chunks = rerank("financial metrics revenue profit margin EBITDA", chunks, top_n=8)
    rerank_latency_ms = round((time.perf_counter() - t_rerank) * 1000, 2)
    top_rerank_score = chunks[0].score if chunks else 0.0

    logger.info(
        "financial_analysis_retrieval_complete",
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
            "metrics": [],
            "financial_health": "Unknown",
            "key_observations": [],
            "summary": "No financial data found.",
            "citations": [],
        }

    # ── Gemini call ──────────────────────────────────────────────────────────
    from app.core.gemini_client import generate_content

    prompt = FINANCIALS_PROMPT.format(context=context_str)
    t_llm = time.perf_counter()
    raw_output = await generate_content(
        prompt=prompt,
        model=settings.GEMINI_ANALYSIS_MODEL,
        temperature=0.1,
        response_mime_type="application/json",
        request_id=request_id,
    )
    llm_latency_ms = round((time.perf_counter() - t_llm) * 1000, 2)
    record_latency("generation", llm_latency_ms)

    logger.info(
        "financial_analysis_llm_complete",
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
            result = {"metrics": [], "summary": raw_output}
    except json.JSONDecodeError:
        result = {"metrics": [], "summary": raw_output}

    result["citations"] = citations
    result["model_used"] = settings.GEMINI_ANALYSIS_MODEL
    result["analyzed_at"] = datetime.now(timezone.utc).isoformat()

    _cache.set(cache_key, result)

    logger.info(
        "financial_analysis_complete",
        project_id=project_id,
        request_id=request_id,
        metric_count=len(result.get("metrics", [])),
    )
    return result
