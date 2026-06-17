# AI Due Diligence Copilot

A **production-grade AI-powered due diligence platform** that enables analysts, investors, and M&A teams to upload company documents and instantly receive source-backed risk assessments, financial analysis, and executive summaries.

**100% free, self-hosted stack.** Zero API costs. All components run locally via Docker Compose.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Docker Compose Network                             │
│                                                                             │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────┐  ┌──────────────────┐   │
│  │  Frontend    │  │   Backend    │  │  Worker   │  │     Ollama       │   │
│  │  Next.js 15  │──│  FastAPI     │──│  Celery   │──│  mistral:7b      │   │
│  │  :3000       │  │  :8000       │  │           │  │  nomic-embed-text│   │
│  └─────────────┘  └──────┬───────┘  └─────┬─────┘  │  :11434          │   │
│                          │                │         └──────────────────┘   │
│                   ┌──────┴───────────────┬┘                               │
│                   │                      │                                 │
│  ┌────────────┐  ┌┴───────────┐  ┌──────┴──────┐  ┌──────────────────┐   │
│  │ PostgreSQL │  │   Qdrant   │  │    Redis    │  │     MinIO        │   │
│  │ 16-alpine  │  │  Vector DB │  │  7-alpine   │  │  S3-compatible   │   │
│  │ :5432      │  │  :6333     │  │  :6379      │  │  :9000 / :9001   │   │
│  └────────────┘  └────────────┘  └─────────────┘  └──────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
Upload PDF ──▶ MinIO Storage ──▶ Celery Worker ──▶ Extract (unstructured)
                                       │
                                       ▼
                               Chunk (hierarchical)
                                       │
                                       ▼
                          Embed (nomic-embed-text via Ollama)
                                       │
                                       ▼
                              Store in Qdrant (dense + BM25 sparse)
                                       │
                                       ▼
Query ──▶ Route ──▶ Hybrid Search ──▶ Rerank (cross-encoder) ──▶ LLM (Ollama) ──▶ Answer
```

---

## Quick Start

### Prerequisites

- **Docker Desktop** with at least **8GB RAM** allocated
- **~10GB disk space** (for model downloads on first run)

### One-Command Setup

```bash
# Clone and start
git clone <repo-url> && cd InvestChat
cp .env.example .env
docker-compose up --build
```

> ⚠️ **First run takes 10-30 minutes** — Ollama downloads `mistral:7b` (~4.1GB) and `nomic-embed-text` (~274MB). Subsequent starts are instant thanks to Docker volume persistence.

### Access

| Service          | URL                        |
|------------------|----------------------------|
| **Frontend**     | http://localhost:3000       |
| **Backend API**  | http://localhost:8000       |
| **API Docs**     | http://localhost:8000/docs  |
| **MinIO Console**| http://localhost:9001       |
| **Qdrant UI**    | http://localhost:6333/dashboard |

---

## Hardware Requirements

| Model | RAM Required | Speed (CPU) | Speed (M2 Pro) | Recommended For |
|---|---|---|---|---|
| `mistral:7b` (default) | 6GB+ | ~18 tok/s | ~35 tok/s | Default — fast, good quality |
| `llama3.1:8b` | 8GB+ | ~15 tok/s | ~30 tok/s | Better reasoning, slightly slower |
| `mixtral:8x7b` | 32GB+ | ~5 tok/s | ~12 tok/s | Best quality, needs lots of RAM |

> **Apple Silicon (M2 Pro)**: Your Mac uses unified memory, so Ollama runs very efficiently. The default `mistral:7b` with 8GB RAM leaves ~2GB for other services, which works well.

---

## Swap LLM Models

Change the model by editing `.env`:

```bash
# Edit .env
OLLAMA_LLM_MODEL=llama3.1:8b    # or mistral:7b, mixtral:8x7b, phi3:mini

# Restart Ollama (it will pull the new model automatically)
docker-compose restart ollama
```

---

## Enable GPU Acceleration (NVIDIA)

Uncomment the GPU block in `docker-compose.yml`:

```yaml
ollama:
  # ...
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: all
            capabilities: [gpu]
```

Then restart: `docker-compose up -d ollama`

> GPU acceleration reduces generation time by **5–10x**.

---

## Database Migrations

```bash
# Generate a new migration after model changes
docker-compose exec backend alembic revision --autogenerate -m "description"

# Apply migrations
docker-compose exec backend alembic upgrade head

# Rollback one migration
docker-compose exec backend alembic downgrade -1
```

> Note: In development, the app auto-creates tables on startup via `Base.metadata.create_all`. Use Alembic for production schema changes.

---

## Run Tests

### Backend (pytest)

```bash
docker-compose exec backend pytest tests/ -v
```

Tests cover:
- **Ingestion pipeline**: Section detection, fiscal year extraction, hierarchical chunking, parent-child relationships, table handling
- **RAG retrieval**: Query routing, context building, deduplication, token limits, citation formatting
- **Auth**: Password hashing, JWT token creation/verification

### Frontend (vitest)

```bash
docker-compose exec frontend npm test
```

Tests cover:
- **Utility functions**: File size formatting, date formatting, status/severity color mapping
- **Zustand stores**: Auth state, project management, chat streaming, UI state

---

## API Reference

All endpoints under `/api/v1/`:

### Auth
| Method | Endpoint | Description |
|---|---|---|
| POST | `/auth/register` | Register a new user |
| POST | `/auth/login` | Login → access + refresh tokens |
| POST | `/auth/refresh` | Refresh access token |

### Projects
| Method | Endpoint | Description |
|---|---|---|
| GET | `/projects` | List all projects |
| POST | `/projects` | Create a project |
| GET | `/projects/{id}` | Get project details |
| DELETE | `/projects/{id}` | Delete project + all data |

### Documents
| Method | Endpoint | Description |
|---|---|---|
| GET | `/projects/{id}/documents` | List documents |
| POST | `/projects/{id}/documents` | Upload document (multipart) |
| GET | `/projects/{id}/documents/{doc_id}` | Get document metadata |
| DELETE | `/projects/{id}/documents/{doc_id}` | Delete document |
| GET | `/projects/{id}/documents/{doc_id}/status` | SSE ingestion stream |

### Analysis
| Method | Endpoint | Description |
|---|---|---|
| POST | `/projects/{id}/analysis/risks` | Run risk assessment |
| POST | `/projects/{id}/analysis/growth` | Run growth analysis |
| POST | `/projects/{id}/analysis/financials` | Run financial extraction |
| POST | `/projects/{id}/analysis/summary` | Generate executive summary |
| GET | `/projects/{id}/analysis/{run_id}` | Get analysis result |

### Chat
| Method | Endpoint | Description |
|---|---|---|
| POST | `/projects/{id}/chat` | SSE streamed chat response |
| GET | `/projects/{id}/chat/history` | Get chat history |

### System
| Method | Endpoint | Description |
|---|---|---|
| GET | `/system/health` | All service statuses |

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://ollama:11434` | Ollama server URL |
| `OLLAMA_LLM_MODEL` | `mistral:7b` | LLM model name |
| `OLLAMA_EMBED_MODEL` | `nomic-embed-text` | Embedding model name |
| `OLLAMA_REQUEST_TIMEOUT` | `300` | LLM request timeout (seconds) |
| `POSTGRES_USER` | `ddcopilot` | PostgreSQL username |
| `POSTGRES_PASSWORD` | `changeme` | PostgreSQL password |
| `POSTGRES_DB` | `ddcopilot` | Database name |
| `QDRANT_HOST` | `qdrant` | Qdrant hostname |
| `QDRANT_PORT` | `6333` | Qdrant REST port |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection URL |
| `MINIO_ENDPOINT` | `minio:9000` | MinIO API endpoint |
| `MINIO_ACCESS_KEY` | `minioadmin` | MinIO access key |
| `MINIO_SECRET_KEY` | `minioadmin` | MinIO secret key |
| `MINIO_BUCKET` | `dd-documents` | Default storage bucket |
| `JWT_SECRET_KEY` | (change this) | JWT signing key |
| `JWT_ALGORITHM` | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Access token TTL |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `30` | Refresh token TTL |
| `MAX_UPLOAD_SIZE_MB` | `200` | Max file upload size |
| `BACKEND_CORS_ORIGINS` | `http://localhost:3000` | Allowed CORS origins |

---

## Tech Stack

| Layer | Technology |
|---|---|
| **LLM** | Ollama (mistral:7b) — local, free |
| **Embeddings** | nomic-embed-text via Ollama — 768-dim, local |
| **Reranking** | cross-encoder/ms-marco-MiniLM-L-6-v2 — local |
| **Vector DB** | Qdrant (self-hosted) — hybrid dense+BM25 |
| **Relational DB** | PostgreSQL 16 |
| **Task Queue** | Celery + Redis |
| **Object Storage** | MinIO (S3-compatible) |
| **Backend** | Python 3.11 + FastAPI |
| **Frontend** | Next.js 15 + TypeScript + Tailwind v4 |
| **State** | Zustand + TanStack Query |
| **Auth** | JWT (access + refresh tokens) |

---

## Project Structure

```
InvestChat/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # REST endpoints
│   │   ├── core/            # Config, security, logging
│   │   ├── db/              # Models, session
│   │   ├── ingestion/       # Extract → Chunk → Embed pipeline
│   │   ├── rag/             # Retriever, reranker, context builder
│   │   ├── analysis/        # Risk, growth, financials, summary, chat
│   │   ├── storage/         # MinIO client
│   │   ├── tasks/           # Celery tasks
│   │   └── main.py          # FastAPI app
│   ├── alembic/             # Database migrations
│   ├── tests/               # pytest suite
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/             # Next.js pages
│   │   ├── components/      # React components
│   │   ├── lib/             # API client, utilities
│   │   ├── stores/          # Zustand state
│   │   └── types/           # TypeScript types
│   ├── package.json
│   └── Dockerfile
├── ollama/
│   └── entrypoint.sh        # Model auto-pull script
├── docker-compose.yml        # Development (8 services)
├── docker-compose.prod.yml   # Production overrides
├── .env.example
└── README.md
```

---

## License

MIT
