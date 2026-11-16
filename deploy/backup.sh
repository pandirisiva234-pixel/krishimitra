#!/usr/bin/env sh
# Daily backup for a Docker deployment: PostgreSQL dump + ChromaDB + uploads.
# Keeps the last 14 days. Schedule with cron, e.g.:
#   0 2 * * * cd /opt/krishimitra && ./deploy/backup.sh >> backups/backup.log 2>&1
set -eu
STAMP=$(date +%Y-%m-%d_%H%M)
DEST="backups/$STAMP"
mkdir -p "$DEST"

docker compose exec -T db pg_dump -U krishimitra -d krishimitra -Fc > "$DEST/krishimitra.dump"
tar -czf "$DEST/knowledge_base.tgz" knowledge_base
docker compose run --rm -v "$(pwd)/$DEST:/backup" --entrypoint sh backend \
  -c "tar -czf /backup/storage.tgz -C /app storage"

find backups -mindepth 1 -maxdepth 1 -type d -mtime +14 -exec rm -rf {} +
echo "Backup written to $DEST"
# Restore the database:  docker compose exec -T db pg_restore -U krishimitra -d krishimitra --clean < backups/<stamp>/krishimitra.dump
