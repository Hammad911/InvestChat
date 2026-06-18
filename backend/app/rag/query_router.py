"""
Query router — classifies incoming queries and maps to retrieval strategies.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class QueryType(str, Enum):
    RISK_ANALYSIS = "risk_analysis"
    FINANCIAL_METRICS = "financial_metrics"
    GROWTH_OPPORTUNITIES = "growth_opportunities"
    COMPARISON = "comparison"
    GENERAL = "general"


@dataclass
class RoutedQuery:
    """A query with routing metadata."""
    original_query: str
    query_type: QueryType
    section_filters: list[str]
    doc_type_filters: list[str]
    enhanced_query: str


# ── Keyword Patterns ─────────────────────────────────────────────────────────
RISK_KEYWORDS = [
    r"\brisk", r"\bthreat", r"\bvulnerab", r"\bexposur", r"\bliabil",
    r"\blitigation", r"\bregulat", r"\bcompliance", r"\blegal",
    r"\bpenalt", r"\bfine\b", r"\bfraud", r"\bbreach",
]

FINANCIAL_KEYWORDS = [
    r"\brevenue", r"\bprofit", r"\bmargin", r"\bebitda", r"\bearning",
    r"\bcash\s*flow", r"\bburn\s*rate", r"\brunway", r"\bcac\b", r"\bltv\b",
    r"\bgross\s*margin", r"\bnet\s*income", r"\bbalance\s*sheet",
    r"\bfinancial", r"\bmetric", r"\bquarter", r"\bfiscal",
]

GROWTH_KEYWORDS = [
    r"\bgrowth", r"\bopportunit", r"\bexpansion", r"\bmarket\s*size",
    r"\btam\b", r"\bsam\b", r"\bsom\b", r"\bscal", r"\bstrateg",
    r"\bcompetitive\s*advantage", r"\bmoat", r"\binnovation",
]

COMPARISON_KEYWORDS = [
    r"\bcompar", r"\bversus\b", r"\bvs\.?\b", r"\bbenchmark",
    r"\bpeer", r"\brelative", r"\bagainst\b", r"\bdifference",
]


def _score_keywords(text: str, patterns: list[str]) -> int:
    """Count keyword pattern matches in text."""
    lower = text.lower()
    return sum(1 for p in patterns if re.search(p, lower))


def route_query(query: str) -> RoutedQuery:
    """
    Classify a query and determine retrieval strategy.
    Uses keyword scoring — fast and deterministic, no LLM call needed.
    """
    risk_score = _score_keywords(query, RISK_KEYWORDS)
    financial_score = _score_keywords(query, FINANCIAL_KEYWORDS)
    growth_score = _score_keywords(query, GROWTH_KEYWORDS)
    comparison_score = _score_keywords(query, COMPARISON_KEYWORDS)

    scores = {
        QueryType.RISK_ANALYSIS: risk_score,
        QueryType.FINANCIAL_METRICS: financial_score,
        QueryType.GROWTH_OPPORTUNITIES: growth_score,
        QueryType.COMPARISON: comparison_score,
    }

    max_score = max(scores.values())

    if max_score == 0:
        query_type = QueryType.GENERAL
    else:
        query_type = max(scores, key=scores.get)

    # Map query type to retrieval filters
    section_filters, doc_type_filters = _get_filters(query_type)

    return RoutedQuery(
        original_query=query,
        query_type=query_type,
        section_filters=section_filters,
        doc_type_filters=doc_type_filters,
        enhanced_query=query,
    )


def _get_filters(query_type: QueryType) -> tuple[list[str], list[str]]:
    """Map query type to metadata filters for retrieval.
    Disabled strict filtering to allow analysis on auto-detected documents."""
    return ([], [])
