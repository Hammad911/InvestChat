"""
Document extraction using unstructured (local) and pdfplumber for tables.
Handles PDF, DOCX, PPTX, XLSX, and TXT files — all processing is local.
"""
from __future__ import annotations

import io
import sys
from dataclasses import dataclass, field
from pathlib import Path

# pdfplumber can hit recursion limits on complex PDFs with nested crops
sys.setrecursionlimit(3000)

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ExtractedElement:
    """A single extracted element from a document."""
    text: str
    element_type: str  # "narrative", "title", "table", "list_item", "header", "footer"
    page_number: int | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class ExtractionResult:
    """Result of document extraction."""
    elements: list[ExtractedElement]
    page_count: int
    tables: list[dict]  # Structured table data
    filename: str = ""


def extract_document(file_bytes: bytes, filename: str) -> ExtractionResult:
    """
    Extract text and tables from a document.
    Dispatches to the appropriate extractor based on file extension.
    """
    ext = Path(filename).suffix.lower()
    logger.info("extraction_start", filename=filename, extension=ext, size=len(file_bytes))

    if ext == ".pdf":
        return _extract_pdf(file_bytes, filename)
    elif ext == ".docx":
        return _extract_docx(file_bytes, filename)
    elif ext == ".pptx":
        return _extract_pptx(file_bytes, filename)
    elif ext == ".xlsx":
        return _extract_xlsx(file_bytes, filename)
    elif ext == ".txt":
        return _extract_txt(file_bytes, filename)
    else:
        raise ValueError(f"Unsupported file type: {ext}")


def _extract_pdf(file_bytes: bytes, filename: str) -> ExtractionResult:
    """Extract from PDF using pdfplumber for text and tables."""
    import pdfplumber

    elements: list[ExtractedElement] = []
    tables: list[dict] = []

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        page_count = len(pdf.pages)

        for page_num, page in enumerate(pdf.pages, 1):
            # ── Extract structured tables first ───────────────────────
            page_tables = page.extract_tables()
            table_bboxes = []
            for t_idx, table in enumerate(page_tables):
                if table and len(table) > 1:
                    headers = [str(h or "").strip() for h in table[0]]
                    rows = []
                    for row in table[1:]:
                        rows.append({
                            headers[j]: str(cell or "").strip()
                            for j, cell in enumerate(row)
                            if j < len(headers)
                        })
                    tables.append({
                        "page_number": page_num,
                        "table_index": t_idx,
                        "headers": headers,
                        "rows": rows,
                    })
                    # Build a text representation of the table too
                    table_text = "\n".join(
                        " | ".join(str(cell or "") for cell in row)
                        for row in table
                    )
                    if table_text.strip():
                        elements.append(ExtractedElement(
                            text=table_text.strip(),
                            element_type="table",
                            page_number=page_num,
                        ))
                    # Track the bounding boxes so we don't double-extract
                    if hasattr(page, "find_tables"):
                        for t in page.find_tables():
                            table_bboxes.append(t.bbox)

            # ── Extract narrative text outside of tables ───────────────
            # Crop out table regions to avoid duplicating content
            text_page = page
            for bbox in table_bboxes:
                try:
                    text_page = text_page.outside_bbox(bbox)
                except Exception:
                    pass

            try:
                raw_text = text_page.extract_text(x_tolerance=2, y_tolerance=2)
            except RecursionError:
                # Some PDFs cause infinite recursion in pdfplumber's
                # cropped page objects — fall back to the full page text
                logger.warning(
                    "pdfplumber_recursion_fallback",
                    page=page_num,
                    msg="Falling back to full page text extraction",
                )
                try:
                    raw_text = page.extract_text(x_tolerance=2, y_tolerance=2)
                except RecursionError:
                    raw_text = None

            if raw_text:
                # Split into paragraphs / lines and classify
                for line in raw_text.split("\n"):
                    line = line.strip()
                    if not line:
                        continue
                    # Heuristic: short ALL-CAPS lines or very short lines are titles
                    if len(line) < 80 and (line.isupper() or line.endswith(":")):
                        etype = "title"
                    elif line.startswith(("•", "-", "*", "–", "◦")):
                        etype = "list_item"
                    else:
                        etype = "narrative"
                    elements.append(ExtractedElement(
                        text=line,
                        element_type=etype,
                        page_number=page_num,
                    ))

    logger.info(
        "extraction_complete",
        filename=filename,
        elements=len(elements),
        tables=len(tables),
        pages=page_count,
    )
    return ExtractionResult(
        elements=elements, page_count=page_count, tables=tables, filename=filename
    )


def _extract_docx(file_bytes: bytes, filename: str) -> ExtractionResult:
    """Extract from DOCX using python-docx."""
    from docx import Document

    doc = Document(io.BytesIO(file_bytes))
    elements: list[ExtractedElement] = []
    tables: list[dict] = []

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        if para.style and para.style.name and "heading" in para.style.name.lower():
            etype = "title"
        else:
            etype = "narrative"
        elements.append(ExtractedElement(text=text, element_type=etype))

    for t_idx, table in enumerate(doc.tables):
        if len(table.rows) > 1:
            headers = [cell.text.strip() for cell in table.rows[0].cells]
            rows = []
            for row in table.rows[1:]:
                rows.append({
                    headers[j]: cell.text.strip()
                    for j, cell in enumerate(row.cells)
                    if j < len(headers)
                })
            tables.append({
                "page_number": None,
                "table_index": t_idx,
                "headers": headers,
                "rows": rows,
            })

    return ExtractionResult(
        elements=elements, page_count=len(doc.paragraphs) // 30 or 1,
        tables=tables, filename=filename,
    )


def _extract_pptx(file_bytes: bytes, filename: str) -> ExtractionResult:
    """Extract from PPTX using python-pptx."""
    from pptx import Presentation

    prs = Presentation(io.BytesIO(file_bytes))
    elements: list[ExtractedElement] = []

    for slide_num, slide in enumerate(prs.slides, 1):
        for shape in slide.shapes:
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    text = para.text.strip()
                    if text:
                        elements.append(ExtractedElement(
                            text=text,
                            element_type="narrative",
                            page_number=slide_num,
                        ))

    return ExtractionResult(
        elements=elements, page_count=len(prs.slides),
        tables=[], filename=filename,
    )


def _extract_xlsx(file_bytes: bytes, filename: str) -> ExtractionResult:
    """Extract from XLSX using openpyxl."""
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    elements: list[ExtractedElement] = []
    tables: list[dict] = []

    for sheet_idx, sheet in enumerate(wb.worksheets):
        rows_data = list(sheet.iter_rows(values_only=True))
        if not rows_data:
            continue

        headers = [str(h or "").strip() for h in rows_data[0]]
        rows = []
        for row in rows_data[1:]:
            rows.append({
                headers[j]: str(cell or "").strip()
                for j, cell in enumerate(row)
                if j < len(headers)
            })
        tables.append({
            "page_number": sheet_idx + 1,
            "table_index": 0,
            "headers": headers,
            "rows": rows,
            "sheet_name": sheet.title,
        })
        # Also add as text elements
        for row in rows:
            text = " | ".join(f"{k}: {v}" for k, v in row.items() if v)
            if text:
                elements.append(ExtractedElement(
                    text=text, element_type="table", page_number=sheet_idx + 1
                ))

    wb.close()
    return ExtractionResult(
        elements=elements, page_count=len(wb.worksheets),
        tables=tables, filename=filename,
    )


def _extract_txt(file_bytes: bytes, filename: str) -> ExtractionResult:
    """Extract from plain text."""
    text = file_bytes.decode("utf-8", errors="replace")
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    elements = [
        ExtractedElement(text=p, element_type="narrative", page_number=1)
        for p in paragraphs
    ]
    return ExtractionResult(
        elements=elements, page_count=1, tables=[], filename=filename,
    )
