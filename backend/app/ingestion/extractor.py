"""
Document extraction using unstructured (local) and pdfplumber for tables.
Handles PDF, DOCX, PPTX, XLSX, and TXT files — all processing is local.
"""
from __future__ import annotations

import io
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

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
    """Extract from PDF using unstructured + pdfplumber for tables."""
    from unstructured.partition.pdf import partition_pdf
    import pdfplumber

    elements: list[ExtractedElement] = []
    tables: list[dict] = []

    # Use unstructured for layout-aware text extraction
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    try:
        raw_elements = partition_pdf(
            filename=tmp_path,
            strategy="fast",  # Use fast strategy for local inference
            include_page_breaks=True,
        )

        page_num = 1
        for el in raw_elements:
            if hasattr(el, "metadata") and hasattr(el.metadata, "page_number"):
                page_num = el.metadata.page_number or page_num

            el_type = type(el).__name__.lower()
            if "title" in el_type:
                etype = "title"
            elif "table" in el_type:
                etype = "table"
            elif "listitem" in el_type or "list" in el_type:
                etype = "list_item"
            elif "header" in el_type:
                etype = "header"
            elif "footer" in el_type:
                etype = "footer"
            else:
                etype = "narrative"

            text = str(el).strip()
            if text:
                elements.append(ExtractedElement(
                    text=text,
                    element_type=etype,
                    page_number=page_num,
                ))

        # Use pdfplumber for structured table extraction
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            page_count = len(pdf.pages)
            for i, page in enumerate(pdf.pages, 1):
                page_tables = page.extract_tables()
                for t_idx, table in enumerate(page_tables):
                    if table and len(table) > 1:
                        # First row as headers, rest as data
                        headers = [str(h or "").strip() for h in table[0]]
                        rows = []
                        for row in table[1:]:
                            rows.append({
                                headers[j]: str(cell or "").strip()
                                for j, cell in enumerate(row)
                                if j < len(headers)
                            })
                        tables.append({
                            "page_number": i,
                            "table_index": t_idx,
                            "headers": headers,
                            "rows": rows,
                        })
    finally:
        Path(tmp_path).unlink(missing_ok=True)

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
