#!/bin/sh

# Run migrations
alembic revision --autogenerate -m "Initial migration"
alembic upgrade head

# Execute command
exec "$@"
