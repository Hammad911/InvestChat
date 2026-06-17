"""
Financial metrics extraction module.
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
) -> dict:
    """Run financial metrics extraction."""
    logger.info("financial_analysis_start", project_id=project_id)

    chunks = hybrid_search(
        query="revenue profit margin EBITDA net income cash flow financial results earnings",
        project_id=project_id,
        top_k=20,
        section_filters=["Financial Statements", "MD&A", "Selected Financial Data", "Table", "Footnotes"],
        doc_type_filters=["filing", "financial"],
    )

    chunks = expand_parent_context(chunks)
    chunks = rerank("financial metrics revenue profit margin EBITDA", chunks, top_n=8)

    context_str, citations = build_context(chunks, max_tokens=3500, doc_name_map=doc_name_map)

    if not context_str:
        return {
            "metrics": [],
            "financial_health": "Unknown",
            "key_observations": [],
            "summary": "No financial data found.",
            "citations": [],
        }

    prompt = FINANCIALS_PROMPT.format(context=context_str)
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
    result["model_used"] = settings.OLLAMA_LLM_MODEL
    result["analyzed_at"] = datetime.now(timezone.utc).isoformat()

    logger.info(
        "financial_analysis_complete",
        project_id=project_id,
        metric_count=len(result.get("metrics", [])),
    )
    return result
