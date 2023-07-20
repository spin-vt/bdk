import os
from datetime import datetime, timedelta


# For production
db_user = os.getenv('POSTGRES_USER')
db_password = os.getenv('POSTGRES_PASSWORD')
db_host = os.getenv('DB_HOST')
db_port = os.getenv('DB_PORT')
DATABASE_URL = f'postgresql://{db_user}:{db_password}@{db_host}:{db_port}/postgres'
BATCH_SIZE = 50000


# For local testing
# db_host = os.getenv('postgres', 'localhost')
# DATABASE_URL = f'postgresql://postgres:db123@{db_host}:5432/postgres'
# BATCH_SIZE = 50000

