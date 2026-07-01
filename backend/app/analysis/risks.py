"""
Risk assessment analysis module.
Produces structured risk output with categories, severity, and source citations.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone

from app.core.config import settings
from app.core.logging import get_logger
from app.core.semantic_cache import SemanticCache, record_latency
from app.rag.context_builder import build_context
from app.rag.query_router import route_query
from app.rag.reranker import rerank
from app.rag.retriever import expand_parent_context, hybrid_search

logger = get_logger(__name__)

_cache = SemanticCache(namespace="risks")

RISK_PROMPT = """You are a senior due diligence analyst. Analyze the provided documents and identify all material risks.

For each risk, provide:
1. risk_category: One of [Financial Risk, Regulatory/Legal Risk, Market Risk, Operational Risk, Management Risk, Technology Risk]
2. severity: One of [High, Medium, Low]
3. description: Clear, specific description of the risk
4. mitigation_notes: Any mentioned mitigating factors
5. source_citations: Reference the source numbers provided in the context

CONTEXT:
{context}

Respond ONLY with a valid JSON object in this exact format:
{{
  "risks": [
    {{
      "risk_category": "Financial Risk",
      "severity": "High",
      "description": "Description of the risk",
      "mitigation_notes": "Any mitigating factors",
      "source_citations": [1, 2]
    }}
  ],
  "overall_risk_level": "High|Medium|Low",
  "summary": "Brief overall risk assessment summary"
}}
"""


async def analyze_risks(
    project_id: str,
    doc_name_map: dict[str, str] | None = None,
    request_id: str | None = None,
) -> dict:
    """
    Run risk analysis on a project's documents.
    Returns structured risk assessment with citations.
    Checks semantic cache before calling Gemini.
    """
    logger.info("risk_analysis_start", project_id=project_id, request_id=request_id)

    # ── Cache lookup ─────────────────────────────────────────────────────────
    cache_key = f"risks:{project_id}"
    t_cache = time.perf_counter()
    cached = _cache.get(cache_key)
    cache_latency_ms = round((time.perf_counter() - t_cache) * 1000, 2)

    if cached is not None:
        logger.info(
            "risk_analysis_cache_hit",
            project_id=project_id,
            request_id=request_id,
            cache_latency_ms=cache_latency_ms,
        )
        return cached

    # ── Retrieval ────────────────────────────────────────────────────────────
    t_retrieval = time.perf_counter()
    routed = route_query("What are the key risks and risk factors?")
    chunks = hybrid_search(
        query="risk factors threats liabilities regulatory compliance legal",
        project_id=project_id,
        top_k=20,
        section_filters=routed.section_filters,
        doc_type_filters=routed.doc_type_filters,
    )
    chunks = expand_parent_context(chunks)
    retrieval_latency_ms = round((time.perf_counter() - t_retrieval) * 1000, 2)
    record_latency("retrieval", retrieval_latency_ms)

    # ── Rerank ───────────────────────────────────────────────────────────────
    t_rerank = time.perf_counter()
    chunks = rerank("key risks and risk factors", chunks, top_n=8)
    rerank_latency_ms = round((time.perf_counter() - t_rerank) * 1000, 2)
    top_rerank_score = chunks[0].score if chunks else 0.0

    logger.info(
        "risk_analysis_retrieval_complete",
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
            "risks": [],
            "overall_risk_level": "Unknown",
            "summary": "No risk-related content found in the uploaded documents.",
            "citations": [],
        }

    # ── Gemini call ──────────────────────────────────────────────────────────
    from app.core.gemini_client import generate_content

    prompt = RISK_PROMPT.format(context=context_str)
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
        "risk_analysis_llm_complete",
        request_id=request_id,
        stage="gemini_generation",
        latency_ms=llm_latency_ms,
        cache_hit=False,
        num_chunks_retrieved=len(chunks),
        rerank_top_score=round(top_rerank_score, 4),
    )

    # ── Parse JSON ───────────────────────────────────────────────────────────
    try:
        json_start = raw_output.find("{")
        json_end = raw_output.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            result = json.loads(raw_output[json_start:json_end])
        else:
            result = {"risks": [], "overall_risk_level": "Unknown", "summary": raw_output}
    except json.JSONDecodeError:
        result = {"risks": [], "overall_risk_level": "Unknown", "summary": raw_output}

    result["citations"] = citations
    result["model_used"] = settings.GEMINI_ANALYSIS_MODEL
    result["analyzed_at"] = datetime.now(timezone.utc).isoformat()

    # ── Store in cache ───────────────────────────────────────────────────────
    _cache.set(cache_key, result)

    logger.info(
        "risk_analysis_complete",
        project_id=project_id,
        request_id=request_id,
        risk_count=len(result.get("risks", [])),
    )
    return result
