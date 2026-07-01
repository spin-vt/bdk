# Deploying BDK

Production runs on two hosts, each with its own compose file in this
directory:

- **web/** — the public-facing box: nginx (TLS termination) and the Flask
  backend under gunicorn. Stateless; everything it serves comes from the
  data host.
- **data/** — the data box: PostgreSQL 16 (PostGIS-capable image, extension
  off until needed), Redis (Celery broker + coordination flags), and the
  Celery worker + beat, colocated with the database because the heavy
  byte-flows are worker↔database.

## The model

CI builds the backend and worker images on every green `main` build and
pushes them to ghcr tagged by commit SHA
(`.github/workflows/docker_push.yml`). **Nothing is built on the hosts** —
they pull the tagged image.

Each host carries a git checkout of this repository at a **pinned commit**
(for the versioned compose files / nginx.conf), owned by the deploy user and
never hand-edited (`deploy.sh` refuses a dirty tree). Deploying a version =
`deploy.sh <role> <git-sha>` on each host, which checks out the SHA, then
`docker compose pull && up -d` with `TAG` = that SHA. Rollback = the same
command with a previous SHA. The hosts need registry read access (a
`docker login ghcr.io` with a read-only token, or public packages).

## Secrets

Real configuration lives ONLY in a `.env` file beside each compose file
(`web/.env`, `data/.env`), created by hand from `env.example` and chmod 600.
It is never committed, never copied off the host, and rotated by editing the
file and re-running `docker compose up -d`. The database and Redis
passwords appear in both hosts' files; everything else is single-host.

## First-time bring-up / restoring from a dump

`restore-and-migrate.sh` builds a production database from a `pg_dump -Fc`
dump: fresh Postgres container, restore, `alembic upgrade head`, then
`legacy_data_policy.py` (marks past-window filings filed and synthesizes
service plans from legacy per-file values — idempotent, safe on every run).
A from-scratch install skips the restore and just lets the entrypoint run
migrations against the empty database.

## Backups

A nightly cron on the data host (see DEPLOYMENT notes; not part of compose):

    pg_dump -Fc -h localhost -U bdk bdk > /backups/bdk-$(date +%F).dump

Keep at least 14 days and copy them off-host.
