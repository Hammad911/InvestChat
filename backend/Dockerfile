# ══════════════════════════════════════════════════════════════════════════════
# AI Due Diligence Copilot — Backend Dockerfile
# ══════════════════════════════════════════════════════════════════════════════
FROM python:3.11-slim

# System dependencies for unstructured, pdfplumber, and general build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libpq-dev \
    poppler-utils \
    tesseract-ocr \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user for production
RUN adduser --disabled-password --gecos "" appuser

EXPOSE 8000

# Default command (overridden by docker-compose)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
