"""
Chat module — conversational Q&A with streaming SSE and inline citations.
Uses the resilient Gemini client for streaming (no retry — SSE is stateful).
"""
from __future__ import annotations

import json
from collections.abc import AsyncGenerator

from app.core.config import settings
from app.core.logging import get_logger
from app.rag.context_builder import build_context
from app.rag.query_router import route_query
from app.rag.reranker import rerank
from app.rag.retriever import expand_parent_context, hybrid_search

logger = get_logger(__name__)

CHAT_SYSTEM_PROMPT = """You are an AI due diligence analyst. Answer questions based ONLY on the provided context documents.

Rules:
1. Only use information from the provided context
2. Cite sources using [Source N] notation inline
3. If the answer isn't in the context, say "I don't have enough information in the uploaded documents to answer this."
4. Be specific and quantitative where possible
5. For financial data, always mention the time period
"""

CHAT_USER_PROMPT = """CONTEXT:
{context}

CONVERSATION HISTORY:
{history}

QUESTION: {question}

Answer the question based on the context above. Include [Source N] citations inline."""


async def chat_completion(
    question: str,
    project_id: str,
    history: list[dict] | None = None,
    doc_name_map: dict[str, str] | None = None,
    request_id: str | None = None,
) -> dict:
    """
    Non-streaming chat completion with citations.
    Returns full response + citations list.
    """
    logger.info("chat_start", project_id=project_id, question_len=len(question), request_id=request_id)

    # Route query and retrieve
    routed = route_query(question)
    chunks = hybrid_search(
        query=question,
        project_id=project_id,
        top_k=15,
        section_filters=routed.section_filters if routed.section_filters else None,
        doc_type_filters=routed.doc_type_filters if routed.doc_type_filters else None,
    )

    chunks = expand_parent_context(chunks)
    chunks = rerank(question, chunks, top_n=6)

    context_str, citations = build_context(chunks, max_tokens=3000, doc_name_map=doc_name_map)

    # Format history
    history_str = ""
    if history:
        for msg in history[-6:]:  # Last 6 messages for context
            role = msg.get("role", "user")
            content = msg.get("content", "")[:500]
            history_str += f"{role.upper()}: {content}\n"

    prompt = CHAT_USER_PROMPT.format(
        context=context_str,
        history=history_str or "No prior conversation.",
        question=question,
    )

    from app.core.gemini_client import generate_content

    answer = await generate_content(
        prompt=prompt,
        model=settings.GEMINI_LLM_MODEL,
        temperature=0.3,
        system_instruction=CHAT_SYSTEM_PROMPT,
        request_id=request_id,
    )

    logger.info("chat_complete", project_id=project_id, answer_len=len(answer), request_id=request_id)

    return {
        "answer": answer,
        "citations": citations,
        "query_type": routed.query_type.value,
        "model_used": settings.GEMINI_LLM_MODEL,
    }


async def chat_stream(
    question: str,
    project_id: str,
    history: list[dict] | None = None,
    doc_name_map: dict[str, str] | None = None,
    request_id: str | None = None,
) -> AsyncGenerator[str, None]:
    """
    Streaming chat completion via SSE.
    Yields SSE-formatted data chunks.
    NOT cached — streaming responses are excluded from semantic cache by design.
    """
    logger.info("chat_stream_start", project_id=project_id, request_id=request_id)

    routed = route_query(question)
    chunks = hybrid_search(
        query=question,
        project_id=project_id,
        top_k=15,
        section_filters=routed.section_filters if routed.section_filters else None,
        doc_type_filters=routed.doc_type_filters if routed.doc_type_filters else None,
    )

    chunks = expand_parent_context(chunks)
    chunks = rerank(question, chunks, top_n=6)

    context_str, citations = build_context(chunks, max_tokens=3000, doc_name_map=doc_name_map)

    history_str = ""
    if history:
        for msg in history[-6:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")[:500]
            history_str += f"{role.upper()}: {content}\n"

    prompt = CHAT_USER_PROMPT.format(
        context=context_str,
        history=history_str or "No prior conversation.",
        question=question,
    )

    # Send citations first
    yield f"data: {json.dumps({'type': 'citations', 'citations': citations})}\n\n"

    # Stream LLM response — uses streaming variant (no retry wrapper)
    from app.core.gemini_client import stream_content

    try:
        response_stream = stream_content(
            prompt=prompt,
            model=settings.GEMINI_LLM_MODEL,
            temperature=0.3,
            system_instruction=CHAT_SYSTEM_PROMPT,
        )
        for chunk in response_stream:
            if chunk.text:
                yield f"data: {json.dumps({'type': 'token', 'content': chunk.text})}\n\n"
    except Exception as exc:
        logger.error("chat_stream_error", error=str(exc), request_id=request_id)
        yield f"data: {json.dumps({'type': 'error', 'message': 'Stream interrupted. Please retry.'})}\n\n"

    yield f"data: {json.dumps({'type': 'done'})}\n\n"
    yield "data: [DONE]\n\n"
