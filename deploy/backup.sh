#!/bin/sh
# Nightly BDK database backup with tiered retention — run from cron on the
# DATA host. Dumps through the running db container (unix-socket auth, so no
# password lives on the host), writes atomically (.part then rename), then
# prunes:
#
#   daily/    every run             kept DAILY_KEEP   days   (default 14)
#   weekly/   Sunday's dump copied  kept WEEKLY_KEEP  weeks  (default 8)
#   monthly/  the 1st's dump copied kept MONTHLY_KEEP months (default 12)
#
# Worst-case disk = (DAILY_KEEP + WEEKLY_KEEP + MONTHLY_KEEP) x dump size.
# Dumps hold provider data — keep them on trusted storage only; copy the
# monthlies off-host.
#
# Cron (as the deploy user):
#   0 3 * * * /opt/bdk/deploy/backup.sh >> /backups/backup.log 2>&1
#
# COMPOSE_DIR overrides where data/.env + the compose project live, for
# running a copy of this script from outside the pinned checkout.
set -eu

BACKUP_ROOT=${BACKUP_ROOT:-/backups}
DAILY_KEEP=${DAILY_KEEP:-14}
WEEKLY_KEEP=${WEEKLY_KEEP:-8}
MONTHLY_KEEP=${MONTHLY_KEEP:-12}
COMPOSE_DIR=${COMPOSE_DIR:-"$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)/data"}

. "$COMPOSE_DIR/.env"
cd "$COMPOSE_DIR"
DBC=$(docker compose --env-file .env ps -q db)
[ -n "$DBC" ] || { echo "db container not running — no backup taken"; exit 1; }

TODAY=$(date +%F)
mkdir -p "$BACKUP_ROOT/daily" "$BACKUP_ROOT/weekly" "$BACKUP_ROOT/monthly"

OUT="$BACKUP_ROOT/daily/bdk-$TODAY.dump"
docker exec "$DBC" pg_dump -Fc -U "$POSTGRES_USER" "$POSTGRES_DB" > "$OUT.part"
[ "$(head -c 5 "$OUT.part")" = "PGDMP" ] || {
  echo "output is not a pg_dump archive — keeping $OUT.part for inspection"
  exit 1
}
mv "$OUT.part" "$OUT"
echo "$TODAY: $(du -h "$OUT" | cut -f1) -> $OUT"

[ "$(date +%u)" = "7" ] && cp "$OUT" "$BACKUP_ROOT/weekly/"
[ "$(date +%d)" = "01" ] && cp "$OUT" "$BACKUP_ROOT/monthly/"

find "$BACKUP_ROOT/daily" -name 'bdk-*.dump' -mtime +"$DAILY_KEEP" -delete
find "$BACKUP_ROOT/weekly" -name 'bdk-*.dump' -mtime +$((WEEKLY_KEEP * 7)) -delete
find "$BACKUP_ROOT/monthly" -name 'bdk-*.dump' -mtime +$((MONTHLY_KEEP * 31)) -delete
find "$BACKUP_ROOT" -name '*.dump.part' -mtime +1 -delete
