"""
Tests for the document ingestion pipeline:
  - Extraction (text + tables)
  - Section detection & chunking
  - Embedding preparation
"""
from __future__ import annotations

import json
import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.ingestion.chunker import (
    Chunk,
    chunk_document,
    detect_fiscal_year,
    detect_section,
    _approx_token_count,
    _split_into_windows,
)
from app.ingestion.extractor import (
    ExtractedElement,
    ExtractionResult,
    _extract_txt,
)


# ══════════════════════════════════════════════════════════════════════════════
# Section Detection
# ══════════════════════════════════════════════════════════════════════════════


class TestSectionDetection:
    def test_detects_risk_factors(self):
        assert detect_section("Item 1A. Risk Factors") == "Risk Factors"

    def test_detects_risk_factors_lowercase(self):
        assert detect_section("item 1a risk factors") == "Risk Factors"

    def test_detects_mda(self):
        result = detect_section(
            "Item 7. Management's Discussion and Analysis of Financial Condition"
        )
        assert result == "MD&A"

    def test_detects_business(self):
        assert detect_section("Item 1. Business") == "Business"

    def test_detects_financial_statements(self):
        assert detect_section("Item 8. Financial Statements and Supplementary Data") == "Financial Statements"

    def test_detects_footnotes(self):
        assert detect_section("Notes to Consolidated Financial Statements") == "Footnotes"

    def test_returns_none_for_regular_text(self):
        assert detect_section("The company was founded in 2010") is None

    def test_detects_forward_looking(self):
        assert detect_section("Forward-Looking Statements") == "Forward-Looking Statements"


# ══════════════════════════════════════════════════════════════════════════════
# Fiscal Year Detection
# ══════════════════════════════════════════════════════════════════════════════


class TestFiscalYearDetection:
    def test_detects_fiscal_year_pattern(self):
        assert detect_fiscal_year("Fiscal Year 2023 Annual Report") == "2023"

    def test_detects_fy_abbreviation(self):
        assert detect_fiscal_year("FY 2022 Results") == "2022"

    def test_detects_year_ended(self):
        assert detect_fiscal_year("For the year ended December 31, 2023") == "2023"

    def test_detects_standalone_year(self):
        assert detect_fiscal_year("Annual report for 2024") == "2024"

    def test_returns_none_for_no_year(self):
        assert detect_fiscal_year("This is regular text without a year") is None

    def test_ignores_old_years(self):
        # Years before 2000 should not match
        result = detect_fiscal_year("Founded in 1985")
        assert result is None


# ══════════════════════════════════════════════════════════════════════════════
# Token Count & Windowing
# ══════════════════════════════════════════════════════════════════════════════


class TestTokenUtils:
    def test_approx_token_count(self):
        text = "hello world this is a test"
        count = _approx_token_count(text)
        assert count > 0
        # 6 words * 1.3 ≈ 7.8
        assert count == int(6 * 1.3)

    def test_split_into_windows_short_text(self):
        text = "hello world"
        windows = _split_into_windows(text, 100, 20)
        assert len(windows) == 1
        assert windows[0] == "hello world"

    def test_split_into_windows_creates_overlap(self):
        words = " ".join(f"word{i}" for i in range(100))
        windows = _split_into_windows(words, 50, 10)
        assert len(windows) > 1
        # Check that windows overlap
        w1_words = set(windows[0].split())
        w2_words = set(windows[1].split())
        overlap = w1_words & w2_words
        assert len(overlap) > 0

    def test_split_empty_text(self):
        assert _split_into_windows("", 100, 20) == []


# ══════════════════════════════════════════════════════════════════════════════
# Chunking
# ══════════════════════════════════════════════════════════════════════════════


class TestChunking:
    def test_chunk_document_creates_chunks(self, sample_extraction_result):
        doc_id = str(uuid.uuid4())
        project_id = str(uuid.uuid4())

        chunks = chunk_document(
            result=sample_extraction_result,
            doc_id=doc_id,
            project_id=project_id,
            doc_type="filing",
        )

        assert len(chunks) > 0
        assert all(isinstance(c, Chunk) for c in chunks)

    def test_chunks_have_required_metadata(self, sample_extraction_result):
        doc_id = str(uuid.uuid4())
        project_id = str(uuid.uuid4())

        chunks = chunk_document(
            result=sample_extraction_result,
            doc_id=doc_id,
            project_id=project_id,
            doc_type="filing",
        )

        for chunk in chunks:
            assert chunk.doc_id == doc_id
            assert chunk.project_id == project_id
            assert chunk.doc_type == "filing"
            assert chunk.section_name is not None
            assert chunk.chunk_index >= 0

    def test_chunks_detect_sections(self, sample_extraction_result):
        chunks = chunk_document(
            result=sample_extraction_result,
            doc_id=str(uuid.uuid4()),
            project_id=str(uuid.uuid4()),
            doc_type="filing",
        )

        section_names = {c.section_name for c in chunks}
        assert "Risk Factors" in section_names or "MD&A" in section_names

    def test_table_chunks_are_flagged(self, sample_extraction_result):
        chunks = chunk_document(
            result=sample_extraction_result,
            doc_id=str(uuid.uuid4()),
            project_id=str(uuid.uuid4()),
            doc_type="filing",
        )

        table_chunks = [c for c in chunks if c.is_table]
        assert len(table_chunks) > 0
        for tc in table_chunks:
            assert tc.section_name == "Table"

    def test_parent_child_relationship(self, sample_extraction_result):
        chunks = chunk_document(
            result=sample_extraction_result,
            doc_id=str(uuid.uuid4()),
            project_id=str(uuid.uuid4()),
            doc_type="filing",
        )

        parents = [c for c in chunks if c.parent_chunk_id is None and not c.is_table]
        children = [c for c in chunks if c.parent_chunk_id is not None]

        assert len(parents) > 0
        assert len(children) > 0

        # Each child should reference a valid parent
        parent_ids = {c.chunk_id for c in parents}
        for child in children:
            assert child.parent_chunk_id in parent_ids

    def test_fiscal_year_detected(self, sample_extraction_result):
        chunks = chunk_document(
            result=sample_extraction_result,
            doc_id=str(uuid.uuid4()),
            project_id=str(uuid.uuid4()),
            doc_type="filing",
        )

        # At least some chunks should have fiscal_year set
        fy_chunks = [c for c in chunks if c.fiscal_year is not None]
        assert len(fy_chunks) > 0
        assert all(c.fiscal_year == "2023" for c in fy_chunks)


# ══════════════════════════════════════════════════════════════════════════════
# Text Extraction
# ══════════════════════════════════════════════════════════════════════════════


class TestTextExtraction:
    def test_extract_txt(self):
        content = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        result = _extract_txt(content.encode(), "test.txt")

        assert result.page_count == 1
        assert len(result.elements) == 3
        assert result.elements[0].text == "First paragraph."
        assert result.elements[1].text == "Second paragraph."

    def test_extract_txt_handles_unicode(self):
        content = "Revenue: €45.2M\n\nGross Margin: 68.4%"
        result = _extract_txt(content.encode("utf-8"), "test.txt")
        assert len(result.elements) == 2
        assert "€" in result.elements[0].text

    def test_extract_txt_empty_file(self):
        result = _extract_txt(b"", "empty.txt")
        assert len(result.elements) == 0
        assert result.page_count == 1
