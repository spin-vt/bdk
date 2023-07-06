#!/bin/sh

# Then start your application
python3 routes.py
# Start Celery worker
celery -A routes.celery worker --loglevel=DEBUG &

