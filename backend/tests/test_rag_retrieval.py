"""
Tests for the RAG query engine:
  - Query routing
  - Context building
  - Retriever data structures
"""
from __future__ import annotations

import uuid

import pytest

from app.rag.query_router import QueryType, RoutedQuery, route_query, _score_keywords
from app.rag.context_builder import build_context, format_citation_reference
from app.rag.retriever import RetrievedChunk


# ══════════════════════════════════════════════════════════════════════════════
# Query Router
# ══════════════════════════════════════════════════════════════════════════════


class TestQueryRouter:
    def test_routes_risk_query(self):
        result = route_query("What are the main risks and threats to the business?")
        assert result.query_type == QueryType.RISK_ANALYSIS

    def test_routes_financial_query(self):
        result = route_query("What was the revenue and EBITDA for FY2023?")
        assert result.query_type == QueryType.FINANCIAL_METRICS

    def test_routes_growth_query(self):
        result = route_query("What growth opportunities exist in the market?")
        assert result.query_type == QueryType.GROWTH_OPPORTUNITIES

    def test_routes_comparison_query(self):
        result = route_query("How does this company compare versus its peers?")
        assert result.query_type == QueryType.COMPARISON

    def test_routes_general_query(self):
        result = route_query("Tell me about the company")
        assert result.query_type == QueryType.GENERAL

    def test_risk_route_has_section_filters(self):
        result = route_query("What regulatory risks exist?")
        assert "Risk Factors" in result.section_filters

    def test_financial_route_has_doc_type_filters(self):
        result = route_query("Show me the revenue numbers")
        assert "filing" in result.doc_type_filters or "financial" in result.doc_type_filters

    def test_preserves_original_query(self):
        query = "What is the burn rate?"
        result = route_query(query)
        assert result.original_query == query

    def test_returns_routed_query_type(self):
        result = route_query("Any litigation risks?")
        assert isinstance(result, RoutedQuery)
        assert isinstance(result.query_type, QueryType)


# ══════════════════════════════════════════════════════════════════════════════
# Context Builder
# ══════════════════════════════════════════════════════════════════════════════


class TestContextBuilder:
    def _make_chunks(self, n=3):
        chunks = []
        for i in range(n):
            chunks.append(RetrievedChunk(
                chunk_id=str(uuid.uuid4()),
                text=f"This is chunk {i} with relevant financial data about revenue of ${i * 10}M.",
                score=0.9 - (i * 0.1),
                doc_id=f"doc-{i}",
                doc_type="filing",
                section_name="MD&A",
                page_number=10 + i,
                is_table=False,
                parent_chunk_id=None,
                fiscal_year="2023",
            ))
        return chunks

    def test_build_context_returns_string_and_citations(self):
        chunks = self._make_chunks()
        context, citations = build_context(chunks)

        assert isinstance(context, str)
        assert isinstance(citations, list)
        assert len(context) > 0
        assert len(citations) > 0

    def test_context_contains_source_headers(self):
        chunks = self._make_chunks()
        context, _ = build_context(chunks)

        assert "[Source 1:" in context
        assert "MD&A" in context

    def test_citations_have_required_fields(self):
        chunks = self._make_chunks()
        _, citations = build_context(chunks)

        for cit in citations:
            assert "citation_index" in cit
            assert "doc_id" in cit
            assert "section" in cit
            assert "page_number" in cit
            assert "excerpt" in cit
            assert "relevance_score" in cit

    def test_uses_doc_name_map(self):
        chunks = self._make_chunks(1)
        name_map = {chunks[0].doc_id: "Acme Corp 10-K 2023"}
        context, citations = build_context(chunks, doc_name_map=name_map)

        assert "Acme Corp 10-K 2023" in context
        assert citations[0]["doc_name"] == "Acme Corp 10-K 2023"

    def test_respects_max_tokens(self):
        # Create many chunks
        chunks = self._make_chunks(20)
        context, citations = build_context(chunks, max_tokens=50)

        # Should truncate to roughly 50 tokens
        word_count = len(context.split())
        assert word_count < 200  # Well under what 20 chunks would produce

    def test_deduplicates_similar_chunks(self):
        c1 = RetrievedChunk(
            chunk_id="1", text="Same text here", score=0.9,
            doc_id="d1", doc_type="filing", section_name="S1",
            page_number=1, is_table=False, parent_chunk_id=None,
            fiscal_year="2023",
        )
        c2 = RetrievedChunk(
            chunk_id="2", text="Same text here", score=0.8,
            doc_id="d1", doc_type="filing", section_name="S1",
            page_number=1, is_table=False, parent_chunk_id=None,
            fiscal_year="2023",
        )
        context, citations = build_context([c1, c2])
        # Should only include one instance
        assert context.count("Same text here") == 1

    def test_empty_chunks(self):
        context, citations = build_context([])
        assert context == ""
        assert citations == []


class TestCitationFormatting:
    def test_format_citation_with_page(self):
        result = format_citation_reference(1, "10-K 2023", "Risk Factors", 34)
        assert "[Source 1:" in result
        assert "10-K 2023" in result
        assert "Page 34" in result

    def test_format_citation_without_page(self):
        result = format_citation_reference(2, "Presentation", "Overview", None)
        assert "[Source 2:" in result
        assert "Page" not in result


# ══════════════════════════════════════════════════════════════════════════════
# Auth Tests (Unit)
# ══════════════════════════════════════════════════════════════════════════════


class TestAuth:
    def test_password_hashing(self):
        from app.core.security import hash_password, verify_password

        password = "test-password-123"
        hashed = hash_password(password)

        assert hashed != password
        assert verify_password(password, hashed)
        assert not verify_password("wrong-password", hashed)

    def test_access_token_creation(self):
        from app.core.security import create_access_token, decode_token

        user_id = str(uuid.uuid4())
        token = create_access_token(user_id)

        assert isinstance(token, str)
        assert len(token) > 0

        payload = decode_token(token)
        assert payload["sub"] == user_id
        assert payload["type"] == "access"

    def test_refresh_token_creation(self):
        from app.core.security import create_refresh_token, decode_token

        user_id = str(uuid.uuid4())
        token = create_refresh_token(user_id)

        payload = decode_token(token)
        assert payload["sub"] == user_id
        assert payload["type"] == "refresh"

    def test_invalid_token_raises(self):
        from app.core.security import decode_token
        from fastapi import HTTPException

        with pytest.raises(HTTPException):
            decode_token("invalid-token-string")
