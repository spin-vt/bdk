import os
from datetime import datetime, timedelta

IN_PRODUCTION = os.getenv('IN_PRODUCTION')

# For production
db_user = os.getenv('POSTGRES_USER')
db_password = os.getenv('POSTGRES_PASSWORD')
db_host = os.getenv('DB_HOST')
db_port = os.getenv('DB_PORT')
db_name = os.getenv('POSTGRES_DB')
backend_port = os.getenv('DEVELOP_BACKEND_PORT')

DATABASE_URL = f'postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}'


BATCH_SIZE = 50000
COOKIE_EXP_TIME = timedelta(days=7)  # Cookie will expire in 7 days


# For local testing
# db_host = os.getenv('postgres', 'localhost')
# DATABASE_URL = f'postgresql://postgres:db123@{db_host}:5432/postgres'
# BATCH_SIZE = 50000
