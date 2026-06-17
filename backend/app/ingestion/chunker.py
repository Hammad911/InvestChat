"""
Hierarchical chunking with SEC section detection.
Parent chunks = full sections, Child chunks = 512-token overlapping windows.
Tables extracted as structured JSON nodes.
"""
from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field

from app.core.logging import get_logger
from app.ingestion.extractor import ExtractedElement, ExtractionResult

logger = get_logger(__name__)

# ── SEC Section Patterns ─────────────────────────────────────────────────────
SEC_SECTION_PATTERNS = [
    (r"(?:item|part)\s*1a[\.\:\s]*risk\s*factors", "Risk Factors"),
    (r"(?:item|part)\s*1b[\.\:\s]*unresolved\s*staff", "Unresolved Staff Comments"),
    (r"(?:item|part)\s*1[\.\:\s]*business", "Business"),
    (r"(?:item|part)\s*2[\.\:\s]*properties", "Properties"),
    (r"(?:item|part)\s*3[\.\:\s]*legal", "Legal Proceedings"),
    (r"(?:item|part)\s*5[\.\:\s]*market", "Market Information"),
    (r"(?:item|part)\s*6[\.\:\s]*selected\s*financial", "Selected Financial Data"),
    (r"(?:item|part)\s*7a[\.\:\s]*quantitative", "Quantitative Disclosures"),
    (r"(?:item|part)\s*7[\.\:\s]*management.?s?\s*discussion", "MD&A"),
    (r"(?:item|part)\s*8[\.\:\s]*financial\s*statements", "Financial Statements"),
    (r"(?:item|part)\s*9[\.\:\s]*changes", "Changes in Accountants"),
    (r"notes?\s*to\s*(?:the\s*)?(?:consolidated\s*)?financial\s*statements", "Footnotes"),
    (r"management.?s?\s*discussion\s*and\s*analysis", "MD&A"),
    (r"risk\s*factors", "Risk Factors"),
    (r"executive\s*summary", "Executive Summary"),
    (r"table\s*of\s*contents", "Table of Contents"),
    (r"forward[- ]looking\s*statements", "Forward-Looking Statements"),
]

# ── Fiscal Year Detection ────────────────────────────────────────────────────
FISCAL_YEAR_PATTERNS = [
    r"(?:fiscal|fy)\s*(?:year)?\s*(\d{4})",
    r"(?:year|period)\s*end(?:ed|ing)\s*\w+\s*\d{1,2},?\s*(\d{4})",
    r"for\s*the\s*year\s*ended\s*\w+\s*\d{1,2},?\s*(\d{4})",
    r"20[12]\d",  # Catch standalone years
]

CHUNK_SIZE = 512  # tokens (approximate by words * 1.3)
CHUNK_OVERLAP = 64


@dataclass
class Chunk:
    """A document chunk ready for embedding."""
    chunk_id: str
    text: str
    doc_id: str
    project_id: str
    doc_type: str
    section_name: str
    page_number: int | None
    chunk_index: int
    is_table: bool
    parent_chunk_id: str | None
    fiscal_year: str | None
    metadata: dict = field(default_factory=dict)


def detect_section(text: str) -> str | None:
    """Detect SEC section name from text using regex patterns."""
    lower = text.lower().strip()
    for pattern, section_name in SEC_SECTION_PATTERNS:
        if re.search(pattern, lower):
            return section_name
    return None


def detect_fiscal_year(text: str) -> str | None:
    """Extract fiscal year from text."""
    for pattern in FISCAL_YEAR_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            year = match.group(1) if match.lastindex else match.group(0)
            if year.isdigit() and 2000 <= int(year) <= 2030:
                return year
    return None


def _approx_token_count(text: str) -> int:
    """Approximate token count (words * 1.3 is a reasonable heuristic)."""
    return int(len(text.split()) * 1.3)


def _split_into_windows(text: str, window_size: int, overlap: int) -> list[str]:
    """Split text into overlapping token windows."""
    words = text.split()
    if not words:
        return []

    # Convert token counts to approximate word counts
    word_window = int(window_size / 1.3)
    word_overlap = int(overlap / 1.3)
    step = max(word_window - word_overlap, 1)

    windows = []
    for i in range(0, len(words), step):
        window = " ".join(words[i : i + word_window])
        if window.strip():
            windows.append(window)
        if i + word_window >= len(words):
            break

    return windows


def chunk_document(
    result: ExtractionResult,
    doc_id: str,
    project_id: str,
    doc_type: str,
) -> list[Chunk]:
    """
    Create hierarchical chunks from extraction results.

    Strategy:
    1. Group elements by detected sections
    2. Create parent chunks (full sections)
    3. Create child chunks (512-token overlapping windows)
    4. Create separate table chunks
    """
    logger.info(
        "chunking_start",
        doc_id=doc_id,
        elements=len(result.elements),
        tables=len(result.tables),
    )

    chunks: list[Chunk] = []
    chunk_index = 0

    # Detect fiscal year from first few elements
    fiscal_year = None
    for el in result.elements[:20]:
        fy = detect_fiscal_year(el.text)
        if fy:
            fiscal_year = fy
            break

    # ── Group elements into sections ─────────────────────────────────
    sections: list[tuple[str, list[ExtractedElement]]] = []
    current_section = "General"
    current_elements: list[ExtractedElement] = []

    for el in result.elements:
        detected = detect_section(el.text)
        if detected and detected != current_section:
            if current_elements:
                sections.append((current_section, current_elements))
            current_section = detected
            current_elements = [el]
        else:
            current_elements.append(el)

    if current_elements:
        sections.append((current_section, current_elements))

    # ── Create parent + child chunks per section ─────────────────────
    for section_name, elements in sections:
        section_text = "\n\n".join(el.text for el in elements)
        if not section_text.strip():
            continue

        # Parent chunk (full section)
        parent_id = str(uuid.uuid4())
        parent_page = elements[0].page_number if elements else None

        chunks.append(Chunk(
            chunk_id=parent_id,
            text=section_text,
            doc_id=doc_id,
            project_id=project_id,
            doc_type=doc_type,
            section_name=section_name,
            page_number=parent_page,
            chunk_index=chunk_index,
            is_table=False,
            parent_chunk_id=None,
            fiscal_year=fiscal_year,
            metadata={"is_parent": True, "element_count": len(elements)},
        ))
        chunk_index += 1

        # Child chunks (overlapping windows)
        if _approx_token_count(section_text) > CHUNK_SIZE:
            windows = _split_into_windows(section_text, CHUNK_SIZE, CHUNK_OVERLAP)
            for window in windows:
                child_id = str(uuid.uuid4())
                chunks.append(Chunk(
                    chunk_id=child_id,
                    text=window,
                    doc_id=doc_id,
                    project_id=project_id,
                    doc_type=doc_type,
                    section_name=section_name,
                    page_number=parent_page,
                    chunk_index=chunk_index,
                    is_table=False,
                    parent_chunk_id=parent_id,
                    fiscal_year=fiscal_year,
                ))
                chunk_index += 1
        else:
            # Section fits in one chunk — create a child pointing to parent
            child_id = str(uuid.uuid4())
            chunks.append(Chunk(
                chunk_id=child_id,
                text=section_text,
                doc_id=doc_id,
                project_id=project_id,
                doc_type=doc_type,
                section_name=section_name,
                page_number=parent_page,
                chunk_index=chunk_index,
                is_table=False,
                parent_chunk_id=parent_id,
                fiscal_year=fiscal_year,
            ))
            chunk_index += 1

    # ── Table chunks ─────────────────────────────────────────────────
    for table in result.tables:
        table_text = json.dumps(table, indent=2)
        table_id = str(uuid.uuid4())
        chunks.append(Chunk(
            chunk_id=table_id,
            text=table_text,
            doc_id=doc_id,
            project_id=project_id,
            doc_type=doc_type,
            section_name="Table",
            page_number=table.get("page_number"),
            chunk_index=chunk_index,
            is_table=True,
            parent_chunk_id=None,
            fiscal_year=fiscal_year,
            metadata={"headers": table.get("headers", [])},
        ))
        chunk_index += 1

    logger.info(
        "chunking_complete",
        doc_id=doc_id,
        total_chunks=len(chunks),
        sections=len(sections),
        table_chunks=len(result.tables),
    )
    return chunks
