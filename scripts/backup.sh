#!/usr/bin/env bash
set -euo pipefail

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="${BACKUP_DIR:-/tmp/pathfinder-backups}"
mkdir -p "$BACKUP_DIR"

# PostgreSQL backup
echo "Backing up PostgreSQL..."
docker compose exec -T postgres pg_dump \
  -U pathfinder pathfinder \
  | gzip > "$BACKUP_DIR/postgres_${TIMESTAMP}.sql.gz"
echo "PostgreSQL backup: $BACKUP_DIR/postgres_${TIMESTAMP}.sql.gz"

# MinIO backup using mc (MinIO client)
echo "Backing up MinIO..."
docker compose exec -T minio mc alias set local http://localhost:9000 minioadmin minioadmin 2>/dev/null || true
docker compose exec -T minio mc mirror local/pathfinder-raw "$BACKUP_DIR/minio_${TIMESTAMP}/"
echo "MinIO backup: $BACKUP_DIR/minio_${TIMESTAMP}/"

echo "Backup complete."
