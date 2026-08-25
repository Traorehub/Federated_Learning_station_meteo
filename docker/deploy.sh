#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

if [ ! -f .env ]; then
  echo "docker/.env manquant : copiez .env.example et remplissez DB_PASSWORD / INGEST_TOKEN" >&2
  exit 1
fi

echo "================================================"
echo "  Federated IoT : déploiement Docker"
echo "================================================"

docker compose build --no-cache api frontend
docker compose down --remove-orphans 2>/dev/null || true
docker rm -f fl_nginx fl_api fl_frontend fl_db 2>/dev/null || true
docker compose up -d --force-recreate --remove-orphans

echo ""
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E 'NAMES|fl_' || docker ps
echo ""
echo -n "Health : "
curl -sf http://localhost:8082/health || echo "échec : docker logs fl_api / fl_nginx"
echo ""
echo "https://federated.near-u-api.org/"
