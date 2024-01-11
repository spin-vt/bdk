#!/bin/sh

# Check if migrations directory exists
if [ ! -d "/app/alembic/versions" ]; then
    mkdir -p /app/alembic/versions
fi

# Generate initial migration script if it does not exist
if [ -z "$(ls -A /app/alembic/versions)" ]; then
   alembic revision --autogenerate -m "Initial migration"
   # Run migrations
   alembic upgrade head
fi
# Execute command
exec "$@"
