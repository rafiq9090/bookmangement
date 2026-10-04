#!/bin/sh
set -eu
umask 077
backup_dir=${1:?Usage: deploy/backup.sh /absolute/protected-backup-directory}
case "$backup_dir" in /*) ;; *) echo "Use an absolute backup directory" >&2; exit 1;; esac
mkdir -p "$backup_dir"
backup_dir=$(cd "$backup_dir" && pwd -P)
repo_dir=$(pwd -P)
case "$backup_dir/" in "$repo_dir/media/"*|"$repo_dir/static/"*|"$repo_dir/staticfiles/"*|"$repo_dir/private_uploads/"*) echo "Backup directory cannot be publicly served or an upload directory" >&2; exit 1;; esac
stamp=$(date -u +%Y%m%dT%H%M%SZ)
docker compose -f docker-compose.production.yml exec -T postgres sh -c 'pg_dump -Fc -U "$POSTGRES_USER" "$POSTGRES_DB"' > "$backup_dir/$stamp-postgres.dump.partial"
mv "$backup_dir/$stamp-postgres.dump.partial" "$backup_dir/$stamp-postgres.dump"
docker compose -f docker-compose.production.yml exec -T web tar -czf - -C /app media private_uploads > "$backup_dir/$stamp-uploads.tar.gz.partial"
mv "$backup_dir/$stamp-uploads.tar.gz.partial" "$backup_dir/$stamp-uploads.tar.gz"
sha256sum "$backup_dir/$stamp-postgres.dump" "$backup_dir/$stamp-uploads.tar.gz" > "$backup_dir/$stamp-checksums.txt"
echo "Backup created. Encrypt and transfer off-host; verify restoration in isolated staging."
