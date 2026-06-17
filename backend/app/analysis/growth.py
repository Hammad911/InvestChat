"""
Growth opportunities analysis module.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.rag.context_builder import build_context
from app.rag.reranker import rerank
from app.rag.retriever import expand_parent_context, hybrid_search

logger = get_logger(__name__)

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
) -> dict:
    """Run growth opportunity analysis."""
    logger.info("growth_analysis_start", project_id=project_id)

    chunks = hybrid_search(
        query="growth opportunities market expansion competitive advantage innovation strategy",
        project_id=project_id,
        top_k=20,
        section_filters=["Business", "Executive Summary", "MD&A", "General"],
        doc_type_filters=["filing", "presentation", "market_report"],
    )

    chunks = expand_parent_context(chunks)
    chunks = rerank("growth opportunities and competitive advantages", chunks, top_n=8)

    context_str, citations = build_context(chunks, max_tokens=3500, doc_name_map=doc_name_map)

    if not context_str:
        return {
            "opportunities": [],
            "market_outlook": "Insufficient data",
            "summary": "No growth-related content found.",
            "citations": [],
        }

    prompt = GROWTH_PROMPT.format(context=context_str)
    response = httpx.post(
        f"{settings.OLLAMA_BASE_URL}/api/generate",
        json={
            "model": settings.OLLAMA_LLM_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.2, "num_predict": 2000},
        },
        timeout=settings.OLLAMA_REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    raw_output = response.json().get("response", "")

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
    result["model_used"] = settings.OLLAMA_LLM_MODEL
    result["analyzed_at"] = datetime.now(timezone.utc).isoformat()

    logger.info(
        "growth_analysis_complete",
        project_id=project_id,
        opportunity_count=len(result.get("opportunities", [])),
    )
    return result
