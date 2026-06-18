"""
Executive summary generation module.
5-section brief: Overview, Business Model, Key Financials, Risk Highlights, Investment Thesis.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from google import genai

from app.core.config import settings
from app.core.logging import get_logger
from app.rag.context_builder import build_context
from app.rag.reranker import rerank
from app.rag.retriever import expand_parent_context, hybrid_search

logger = get_logger(__name__)

SUMMARY_PROMPT = """You are a senior investment analyst preparing an executive briefing. Create a comprehensive summary from the provided documents.

Structure your summary into exactly 5 sections:
1. Company Overview - What the company does, market position
2. Business Model - How it generates revenue, key value propositions
3. Key Financials - Critical financial figures and trends
4. Risk Highlights - Top 3-5 material risks
5. Investment Thesis - Bull case vs bear case for investment

For each section, cite specific sources using [Source N] references.

CONTEXT:
{context}

Respond ONLY with a valid JSON object:
{{
  "sections": [
    {{
      "title": "Company Overview",
      "content": "Summary text with [Source 1] citations...",
      "source_citations": [1, 2]
    }},
    {{
      "title": "Business Model",
      "content": "...",
      "source_citations": [2, 3]
    }},
    {{
      "title": "Key Financials",
      "content": "...",
      "source_citations": [4]
    }},
    {{
      "title": "Risk Highlights",
      "content": "...",
      "source_citations": [1, 5]
    }},
    {{
      "title": "Investment Thesis",
      "content": "...",
      "source_citations": [1, 2, 3]
    }}
  ],
  "one_liner": "One-sentence company summary",
  "recommendation": "Brief investment recommendation"
}}
"""


async def analyze_summary(
    project_id: str,
    doc_name_map: dict[str, str] | None = None,
) -> dict:
    """Generate executive summary."""
    logger.info("summary_analysis_start", project_id=project_id)

    # Broad search across all document types
    chunks = hybrid_search(
        query="company overview business model revenue risk investment",
        project_id=project_id,
        top_k=25,
    )

    chunks = expand_parent_context(chunks)
    chunks = rerank(
        "company overview business model financial performance risks investment thesis",
        chunks,
        top_n=10,
    )

    context_str, citations = build_context(chunks, max_tokens=4000, doc_name_map=doc_name_map)

    if not context_str:
        return {
            "sections": [],
            "one_liner": "Insufficient data for summary.",
            "recommendation": "More documents needed.",
            "citations": [],
        }

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    prompt = SUMMARY_PROMPT.format(context=context_str)
    
    response = client.models.generate_content(
        model=settings.GEMINI_LLM_MODEL,
        contents=prompt,
        config=genai.types.GenerateContentConfig(
            temperature=0.2,
            response_mime_type="application/json",
        ),
    )
    raw_output = response.text

    try:
        json_start = raw_output.find("{")
        json_end = raw_output.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            result = json.loads(raw_output[json_start:json_end])
        else:
            result = {"sections": [], "summary": raw_output}
    except json.JSONDecodeError:
        result = {"sections": [], "summary": raw_output}

    result["citations"] = citations
    result["model_used"] = settings.GEMINI_LLM_MODEL
    result["analyzed_at"] = datetime.now(timezone.utc).isoformat()

    logger.info(
        "summary_analysis_complete",
        project_id=project_id,
        section_count=len(result.get("sections", [])),
    )
    return result
