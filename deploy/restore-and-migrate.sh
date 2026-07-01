#!/bin/sh
# One-off bring-up of the production database from a pg_dump -Fc dump, run on
# the DATA host after `docker compose up -d db` and before starting anything
# else. Restores into the running db container, runs migrations, then the
# legacy data policy. Idempotent up to the restore (refuses a non-empty DB).
#
#   ./restore-and-migrate.sh /path/to/dump.dump
set -eu

DUMP=${1:?usage: restore-and-migrate.sh <dump-file>}
DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
. "$DIR/data/.env" 2>/dev/null || true
DB=${POSTGRES_DB:?data/.env must define POSTGRES_DB}
# The worker image (used for migrations + the data policy) is tagged by the
# checked-out commit, matching deploy.sh.
TAG=$(git -C "$DIR" rev-parse HEAD)
export TAG

cd "$DIR/data"
DBC=$(docker compose --env-file .env ps -q db)
[ -n "$DBC" ] || { echo "db container not running (docker compose up -d db first)"; exit 1; }

TABLES=$(docker exec "$DBC" psql -U "$POSTGRES_USER" -d "$DB" -tAc \
  "SELECT count(*) FROM pg_tables WHERE schemaname='public'")
[ "$TABLES" = "0" ] || { echo "database is not empty ($TABLES tables) — refusing to restore"; exit 1; }

echo "== restore (postgis/topology/spatial_ref_sys filtered: the extension is
   unused; enabling PostGIS later is a one-line migration) =="
docker cp "$DUMP" "$DBC":/tmp/restore.dump
docker exec "$DBC" sh -c "
  pg_restore -l /tmp/restore.dump | grep -viE 'postgis|topology|spatial_ref_sys' > /tmp/toc.list &&
  pg_restore -U $POSTGRES_USER -d $DB -j 4 -L /tmp/toc.list /tmp/restore.dump &&
  rm /tmp/restore.dump"

echo "== migrations =="
docker compose --env-file .env run --rm --no-deps \
  --entrypoint sh worker -c "cd /app && alembic upgrade head"

echo "== legacy data policy (filed status + plan synthesis; idempotent) =="
docker compose --env-file .env run --rm --no-deps \
  --entrypoint python3 worker /app/scripts/legacy_data_policy.py

echo "== done — start the rest: docker compose --env-file .env up -d =="
