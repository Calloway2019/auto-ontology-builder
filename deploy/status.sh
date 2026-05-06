#!/bin/bash
# ============================================================
# Auto Ontology Builder & QA System - Status Check
# Usage: chmod +x status.sh && ./status.sh
# ============================================================

NETWORK="ontology-net"
CONTAINERS="ontology-neo4j ontology-backend ontology-frontend"

echo "=========================================="
echo " Container Status"
echo "=========================================="
echo ""

for container in $CONTAINERS; do
    if docker ps --format '{{.Names}}' --filter name="$container" | grep -q "$container"; then
        status=$(docker ps --format '{{.Status}}' --filter name="$container")
        echo "  [RUNNING]  ${container} - ${status}"
    elif docker ps -a --format '{{.Names}}' --filter name="$container" | grep -q "$container"; then
        status=$(docker ps -a --format '{{.Status}}' --filter name="$container")
        echo "  [STOPPED]  ${container} - ${status}"
    else
        echo "  [MISSING]  ${container}"
    fi
done

echo ""
echo "=========================================="
echo " Network"
echo "=========================================="
echo ""
docker network inspect "$NETWORK" --format '{{range .IPAM.Config}}{{.Subnet}}{{end}}' 2>/dev/null && \
    echo "  Network ${NETWORK} exists" || echo "  Network ${NETWORK} not found"

echo ""
echo "=========================================="
echo " Data Directory"
echo "=========================================="
echo ""
if [ -d "/opt/ontology-qa/data" ]; then
    du -sh /opt/ontology-qa/data/
    echo ""
    ls -la /opt/ontology-qa/data/
else
    echo "  Data directory not found"
fi

echo ""
echo "=========================================="
echo " Backend Logs (last 10 lines)"
echo "=========================================="
docker logs --tail 10 ontology-backend 2>/dev/null || echo "  No logs available"
