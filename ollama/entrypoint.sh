#!/bin/sh
# ══════════════════════════════════════════════════════════════════════════════
# Ollama Entrypoint Script
# Starts the Ollama server and pulls required models if not already cached.
# Models persist via Docker volume mount at /root/.ollama
# ══════════════════════════════════════════════════════════════════════════════

set -e

LLM_MODEL="${OLLAMA_LLM_MODEL:-mistral:7b}"
EMBED_MODEL="${OLLAMA_EMBED_MODEL:-nomic-embed-text}"

echo "═══════════════════════════════════════════════════════════════"
echo "  Ollama Entrypoint"
echo "  LLM Model:   $LLM_MODEL"
echo "  Embed Model: $EMBED_MODEL"
echo "═══════════════════════════════════════════════════════════════"

# Start Ollama server in background
echo "[1/4] Starting Ollama server..."
ollama serve &
SERVER_PID=$!

# Wait for server to be ready
echo "[2/4] Waiting for Ollama server to be ready..."
MAX_RETRIES=30
RETRY_COUNT=0
until curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ "$RETRY_COUNT" -ge "$MAX_RETRIES" ]; then
        echo "ERROR: Ollama server failed to start after ${MAX_RETRIES} attempts"
        exit 1
    fi
    echo "  Waiting... (attempt $RETRY_COUNT/$MAX_RETRIES)"
    sleep 2
done
echo "  Ollama server is ready!"

# Pull LLM model if not cached
echo "[3/4] Checking LLM model: $LLM_MODEL"
if ollama list | grep -q "$LLM_MODEL"; then
    echo "  Model $LLM_MODEL already cached"
else
    echo "  Pulling $LLM_MODEL (this may take several minutes on first run)..."
    ollama pull "$LLM_MODEL"
    echo "  Model $LLM_MODEL pulled successfully"
fi

# Pull embedding model if not cached
echo "[4/4] Checking embedding model: $EMBED_MODEL"
if ollama list | grep -q "$EMBED_MODEL"; then
    echo "  Model $EMBED_MODEL already cached"
else
    echo "  Pulling $EMBED_MODEL..."
    ollama pull "$EMBED_MODEL"
    echo "  Model $EMBED_MODEL pulled successfully"
fi

echo "═══════════════════════════════════════════════════════════════"
echo "  All models ready. Ollama is serving on :11434"
echo "═══════════════════════════════════════════════════════════════"

# Keep the server in the foreground
wait $SERVER_PID
