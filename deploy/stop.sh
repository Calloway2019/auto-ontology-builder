#!/bin/bash
# ============================================================
# Auto Ontology Builder & QA System - Stop & Remove Script
# Usage: chmod +x stop.sh && ./stop.sh
# ============================================================

NETWORK="ontology-net"
CONTAINERS="ontology-frontend ontology-backend ontology-neo4j"

echo "Stopping containers..."
for container in $CONTAINERS; do
    if docker ps -q --filter name="$container" > /dev/null 2>&1; then
        docker stop "$container"
        echo "  Stopped ${container}"
    fi
done

echo "Removing containers..."
for container in $CONTAINERS; do
    if docker ps -a --format '{{.Names}}' | grep -q "^${container}$"; then
        docker rm "$container"
        echo "  Removed ${container}"
    fi
done

echo "Removing Docker network..."
docker network rm "$NETWORK" 2>/dev/null && echo "  Network removed" || echo "  Network not found"

echo "Done. Data is preserved in /opt/ontology-qa/data (or your configured DATA_DIR)"
echo "To remove data as well: rm -rf /opt/ontology-qa/data"
