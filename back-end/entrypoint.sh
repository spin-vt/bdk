#!/bin/sh

# Apply committed database migrations, then run the given command.
#
# Migrations live in alembic/versions and are created explicitly with
# `alembic revision --autogenerate -m "..."`. We do NOT auto-generate a
# migration at startup — that produced nondeterministic schemas depending on
# whether the versions dir happened to be empty.
alembic upgrade head

exec "$@"
