#!/usr/bin/env bash
# VI-qism: kunlik pg_dump backup, 7 kunlik saqlash.
# Cron orqali ishlatish: 0 3 * * * /path/to/rasch_bot/scripts/backup.sh
set -euo pipefail

cd "$(dirname "$0")/.."
BACKUP_DIR="./backups"
mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
FILE="$BACKUP_DIR/rasch_bot_${TIMESTAMP}.sql.gz"

docker compose exec -T postgres pg_dump -U "$(grep '^DB_USER=' .env | cut -d= -f2)" "$(grep '^DB_NAME=' .env | cut -d= -f2)" \
  | gzip > "$FILE"

echo "✅ Backup saqlandi: $FILE"

# 7 kundan eski backuplarni o'chirish
find "$BACKUP_DIR" -name "rasch_bot_*.sql.gz" -mtime +7 -delete
