"""
Test fixtures and configuration for pytest.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.db.models import (
    Base,
    User,
    Project,
    Document,
    DocType,
    IngestionStatus,
)
from app.ingestion.chunker import Chunk
from app.ingestion.extractor import ExtractedElement, ExtractionResult


# ── Async event loop fixture ────────────────────────────────────────────────

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ── Sample data fixtures ────────────────────────────────────────────────────

@pytest.fixture
def sample_user_id():
    return str(uuid.uuid4())


@pytest.fixture
def sample_project_id():
    return str(uuid.uuid4())


@pytest.fixture
def sample_doc_id():
    return str(uuid.uuid4())


@pytest.fixture
def sample_extraction_result():
    """A realistic extraction result from a mock SEC filing."""
    return ExtractionResult(
        elements=[
            ExtractedElement(
                text="Item 1A. Risk Factors",
                element_type="title",
                page_number=15,
            ),
            ExtractedElement(
                text="Our business is subject to various risks and uncertainties. "
                "The following risk factors describe significant risks that could "
                "materially affect our financial condition, results of operations, "
                "or business prospects. Investors should carefully consider these "
                "risks before making investment decisions.",
                element_type="narrative",
                page_number=15,
            ),
            ExtractedElement(
                text="We face intense competition in our markets. Our competitors "
                "include large, well-established companies with significantly greater "
                "financial, technical, and marketing resources than we possess. "
                "Increased competition could result in pricing pressure, reduced "
                "margins, and loss of market share.",
                element_type="narrative",
                page_number=16,
            ),
            ExtractedElement(
                text="Regulatory changes could impact our operations. We are subject "
                "to extensive regulation at the federal, state, and local levels. "
                "Changes in regulations or the adoption of new regulations could "
                "increase our compliance costs and negatively impact our results.",
                element_type="narrative",
                page_number=17,
            ),
            ExtractedElement(
                text="Item 7. Management's Discussion and Analysis of Financial "
                "Condition and Results of Operations",
                element_type="title",
                page_number=28,
            ),
            ExtractedElement(
                text="Revenue for fiscal year 2023 was $45.2 million, representing "
                "a 23% increase year-over-year from $36.7 million in fiscal year 2022. "
                "This growth was primarily driven by increased customer acquisition "
                "and expansion of existing accounts.",
                element_type="narrative",
                page_number=28,
            ),
            ExtractedElement(
                text="Gross margin improved to 68.4% in FY2023 from 64.1% in FY2022, "
                "driven by economies of scale and improved operational efficiency. "
                "EBITDA was $8.9 million, up from $5.2 million in the prior year.",
                element_type="narrative",
                page_number=29,
            ),
        ],
        page_count=52,
        tables=[
            {
                "page_number": 30,
                "table_index": 0,
                "headers": ["Metric", "FY2023", "FY2022", "Change"],
                "rows": [
                    {"Metric": "Revenue", "FY2023": "$45.2M", "FY2022": "$36.7M", "Change": "+23%"},
                    {"Metric": "Gross Margin", "FY2023": "68.4%", "FY2022": "64.1%", "Change": "+4.3pp"},
                    {"Metric": "EBITDA", "FY2023": "$8.9M", "FY2022": "$5.2M", "Change": "+71%"},
                ],
            }
        ],
        filename="acme-corp-10k-2023.pdf",
    )


@pytest.fixture
def sample_chunks(sample_doc_id, sample_project_id):
    """Pre-built chunks for testing embedding and retrieval."""
    return [
        Chunk(
            chunk_id=str(uuid.uuid4()),
            text="We face intense competition in our markets. Our competitors include large companies.",
            doc_id=sample_doc_id,
            project_id=sample_project_id,
            doc_type="filing",
            section_name="Risk Factors",
            page_number=16,
            chunk_index=0,
            is_table=False,
            parent_chunk_id=str(uuid.uuid4()),
            fiscal_year="2023",
        ),
        Chunk(
            chunk_id=str(uuid.uuid4()),
            text="Revenue for fiscal year 2023 was $45.2 million, a 23% increase year-over-year.",
            doc_id=sample_doc_id,
            project_id=sample_project_id,
            doc_type="filing",
            section_name="MD&A",
            page_number=28,
            chunk_index=1,
            is_table=False,
            parent_chunk_id=str(uuid.uuid4()),
            fiscal_year="2023",
        ),
    ]


@pytest.fixture
def mock_ollama_embed_response():
    """Mock response from Ollama embedding endpoint."""
    return {
        "embeddings": [[0.1] * 768, [0.2] * 768],
    }


@pytest.fixture
def mock_ollama_generate_response():
    """Mock response from Ollama generation endpoint."""
    return {
        "response": '{"risks": [{"risk_category": "Market Risk", "severity": "High", '
        '"description": "Intense competition", "mitigation_notes": "Strong brand", '
        '"source_citations": [1]}], "overall_risk_level": "Medium", '
        '"summary": "Moderate risk profile"}',
        "done": True,
    }
