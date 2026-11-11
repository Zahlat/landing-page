#!/bin/sh
# One compressed database dump per run; dumps older than BACKUP_KEEP_DAYS are removed.
set -eu

file="/backups/meraki-$(date -u +%Y%m%dT%H%M%SZ).dump"
pg_dump --host=db --username="$PGUSER" --dbname="$POSTGRES_DB" --format=custom --file="$file.tmp"
mv "$file.tmp" "$file"
find /backups -name 'meraki-*.dump' -mtime +"${BACKUP_KEEP_DAYS:-14}" -delete
echo "backup_ok file=$(basename "$file") bytes=$(wc -c < "$file")"
