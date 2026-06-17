"""
Risk assessment analysis module.
Produces structured risk output with categories, severity, and source citations.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.rag.context_builder import build_context
from app.rag.query_router import QueryType, route_query
from app.rag.reranker import rerank
from app.rag.retriever import expand_parent_context, hybrid_search

logger = get_logger(__name__)

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
) -> dict:
    """
    Run risk analysis on a project's documents.
    Returns structured risk assessment with citations.
    """
    logger.info("risk_analysis_start", project_id=project_id)

    # Retrieve risk-relevant chunks
    routed = route_query("What are the key risks and risk factors?")
    chunks = hybrid_search(
        query="risk factors threats liabilities regulatory compliance legal",
        project_id=project_id,
        top_k=20,
        section_filters=routed.section_filters,
        doc_type_filters=routed.doc_type_filters,
    )

    # Expand parent context and rerank
    chunks = expand_parent_context(chunks)
    chunks = rerank("key risks and risk factors", chunks, top_n=8)

    # Build context
    context_str, citations = build_context(chunks, max_tokens=3500, doc_name_map=doc_name_map)

    if not context_str:
        return {
            "risks": [],
            "overall_risk_level": "Unknown",
            "summary": "No risk-related content found in the uploaded documents.",
            "citations": [],
        }

    # Call Ollama LLM
    prompt = RISK_PROMPT.format(context=context_str)
    response = httpx.post(
        f"{settings.OLLAMA_BASE_URL}/api/generate",
        json={
            "model": settings.OLLAMA_LLM_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 2000},
        },
        timeout=settings.OLLAMA_REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    raw_output = response.json().get("response", "")

    # Parse JSON from LLM output
    try:
        # Try to extract JSON from the response
        json_start = raw_output.find("{")
        json_end = raw_output.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            result = json.loads(raw_output[json_start:json_end])
        else:
            result = {"risks": [], "overall_risk_level": "Unknown", "summary": raw_output}
    except json.JSONDecodeError:
        result = {"risks": [], "overall_risk_level": "Unknown", "summary": raw_output}

    result["citations"] = citations
    result["model_used"] = settings.OLLAMA_LLM_MODEL
    result["analyzed_at"] = datetime.now(timezone.utc).isoformat()

    logger.info(
        "risk_analysis_complete",
        project_id=project_id,
        risk_count=len(result.get("risks", [])),
    )
    return result
