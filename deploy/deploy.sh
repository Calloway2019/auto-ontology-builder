#!/bin/bash
# ============================================================
# Auto Ontology Builder & QA System - Offline Deploy Script
# Usage: chmod +x deploy.sh && ./deploy.sh
# ============================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"

# Load environment variables
if [ -f "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE"
    set +a
    echo "[INFO] Loaded .env configuration"
else
    echo "[WARN] .env not found, using defaults"
fi

# Defaults
NEO4J_PASSWORD="${NEO4J_PASSWORD:-ontology-qa-password}"
LLM_API_KEY="${LLM_API_KEY:-your-api-key-here}"
LLM_BASE_URL="${LLM_BASE_URL:-http://172.16.2.237:80/xlm-gateway-ypxikm/sfm-api-gateway/gateway/compatible-mode/v1}"
LLM_MODEL_NAME="${LLM_MODEL_NAME:-qwen-7b}"
LLM_TEMPERATURE="${LLM_TEMPERATURE:-0.1}"
LLM_MAX_TOKENS="${LLM_MAX_TOKENS:-4096}"
LLM_TIMEOUT="${LLM_TIMEOUT:-120}"
DATA_DIR="${DATA_DIR:-/opt/ontology-qa/data}"

# Image files
BACKEND_TAR="ontology-qa-backend.tar"
FRONTEND_TAR="ontology-qa-frontend.tar"
NEO4J_TAR="neo4j-5.23-community.tar"

BACKEND_IMG="ontology-qa-backend:latest"
FRONTEND_IMG="ontology-qa-frontend:latest"
NEO4J_IMG="neo4j:5.23-community"

# Network & containers
NETWORK="ontology-net"
NEO4J_CONTAINER="ontology-neo4j"
BACKEND_CONTAINER="ontology-backend"
FRONTEND_CONTAINER="ontology-frontend"

# ============================================================
echo ""
echo "=========================================="
echo " Auto Ontology Builder - Deployment"
echo "=========================================="
echo ""

# ---------- Step 1: Load Docker images ----------
echo "[1/6] Loading Docker images..."

for tar_file in "$NEO4J_TAR" "$BACKEND_TAR" "$FRONTEND_TAR"; do
    tar_path="${SCRIPT_DIR}/${tar_file}"
    if [ -f "$tar_path" ]; then
        echo "  Loading ${tar_file}..."
        docker load -i "$tar_path"
    else
        echo "  [WARN] ${tar_file} not found, skipping"
    fi
done

# Verify images exist
for img in "$NEO4J_IMG" "$BACKEND_IMG" "$FRONTEND_IMG"; do
    if docker image inspect "$img" > /dev/null 2>&1; then
        echo "  [OK] ${img}"
    else
        echo "  [ERROR] ${img} not found after load"
        exit 1
    fi
done

# ---------- Step 2: Create Docker network ----------
echo "[2/6] Creating Docker network..."

if docker network inspect "$NETWORK" > /dev/null 2>&1; then
    echo "  Network ${NETWORK} already exists, reusing"
else
    docker network create "$NETWORK"
    echo "  Network ${NETWORK} created"
fi

# ---------- Step 3: Create data directories ----------
echo "[3/6] Creating data directories..."

mkdir -p "${DATA_DIR}/uploads"
mkdir -p "${DATA_DIR}/neo4j/data"
mkdir -p "${DATA_DIR}/neo4j/logs"

echo "  ${DATA_DIR}/"
echo "  ├── uploads/       (uploaded files)"
echo "  ├── neo4j/data/    (Neo4j database)"
echo "  └── neo4j/logs/    (Neo4j logs)"

# ---------- Step 4: Start Neo4j ----------
echo "[4/6] Starting Neo4j..."

# Stop existing container if present
if docker ps -a --format '{{.Names}}' | grep -q "^${NEO4J_CONTAINER}$"; then
    echo "  Stopping existing ${NEO4J_CONTAINER}..."
    docker rm -f "$NEO4J_CONTAINER" > /dev/null 2>&1
fi

docker run -d \
    --name "$NEO4J_CONTAINER" \
    --network "$NETWORK" \
    --restart unless-stopped \
    -p 7474:7474 \
    -p 7687:7687 \
    -e NEO4J_AUTH="neo4j/${NEO4J_PASSWORD}" \
    -e NEO4J_PLUGINS='["apoc"]' \
    -e NEO4J_server_memory_heap_initial__size="1G" \
    -e NEO4J_server_memory_heap_max__size="4G" \
    -e NEO4J_server_memory_pagecache_size="1G" \
    -v "${DATA_DIR}/neo4j/data:/data" \
    -v "${DATA_DIR}/neo4j/logs:/logs" \
    "$NEO4J_IMG"

echo "  ${NEO4J_CONTAINER} started, waiting for health check..."

# Wait for Neo4j to be ready
MAX_WAIT=120
WAITED=0
while [ $WAITED -lt $MAX_WAIT ]; do
    if docker exec "$NEO4J_CONTAINER" cypher-shell -u neo4j -p "$NEO4J_PASSWORD" "RETURN 1" > /dev/null 2>&1; then
        echo "  Neo4j is ready (${WAITED}s)"
        break
    fi
    sleep 5
    WAITED=$((WAITED + 5))
    echo "  Waiting... (${WAITED}s)"
done

if [ $WAITED -ge $MAX_WAIT ]; then
    echo "  [WARN] Neo4j did not become ready in ${MAX_WAIT}s, continuing anyway"
fi

# ---------- Step 5: Start Backend ----------
echo "[5/6] Starting Backend..."

if docker ps -a --format '{{.Names}}' | grep -q "^${BACKEND_CONTAINER}$"; then
    echo "  Stopping existing ${BACKEND_CONTAINER}..."
    docker rm -f "$BACKEND_CONTAINER" > /dev/null 2>&1
fi

docker run -d \
    --name "$BACKEND_CONTAINER" \
    --network "$NETWORK" \
    --network-alias backend \
    --restart unless-stopped \
    -p 8000:8000 \
    -e NEO4J_URI="bolt://${NEO4J_CONTAINER}:7687" \
    -e NEO4J_USER=neo4j \
    -e NEO4J_PASSWORD="${NEO4J_PASSWORD}" \
    -e NEO4J_DATABASE=neo4j \
    -e LLM_API_KEY="${LLM_API_KEY}" \
    -e LLM_BASE_URL="${LLM_BASE_URL}" \
    -e LLM_MODEL_NAME="${LLM_MODEL_NAME}" \
    -e LLM_TEMPERATURE="${LLM_TEMPERATURE}" \
    -e LLM_MAX_TOKENS="${LLM_MAX_TOKENS}" \
    -e LLM_TIMEOUT="${LLM_TIMEOUT}" \
    -e UPLOAD_DIR=/app/data/uploads \
    -e DATABASE_URL=sqlite:////app/data/metadata.db \
    -e DEBUG=false \
    -v "${DATA_DIR}/uploads:/app/data/uploads" \
    -v "${DATA_DIR}:/app/data" \
    "$BACKEND_IMG"

echo "  ${BACKEND_CONTAINER} started"

# ---------- Step 6: Start Frontend ----------
echo "[6/6] Starting Frontend..."

if docker ps -a --format '{{.Names}}' | grep -q "^${FRONTEND_CONTAINER}$"; then
    echo "  Stopping existing ${FRONTEND_CONTAINER}..."
    docker rm -f "$FRONTEND_CONTAINER" > /dev/null 2>&1
fi

docker run -d \
    --name "$FRONTEND_CONTAINER" \
    --network "$NETWORK" \
    --restart unless-stopped \
    -p 80:80 \
    "$FRONTEND_IMG"

echo "  ${FRONTEND_CONTAINER} started"

# ---------- Done ----------
echo ""
echo "=========================================="
echo " Deployment Complete!"
echo "=========================================="
echo ""
echo "Access URLs:"
echo "  Frontend:  http://<HOST_IP>:80"
echo "  Backend:   http://<HOST_IP>:8000"
echo "  Neo4j:     http://<HOST_IP>:7474"
echo ""
echo "Data directory: ${DATA_DIR}"
echo ""
echo "To stop all containers, run:"
echo "  ./stop.sh"
echo ""
