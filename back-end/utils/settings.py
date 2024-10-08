import os
from datetime import datetime, timedelta
from urllib.parse import quote_plus

IN_PRODUCTION = os.getenv('IN_PRODUCTION')

# For production
db_user = os.getenv('POSTGRES_USER')
db_password = quote_plus(os.getenv('POSTGRES_PASSWORD'))
db_host = os.getenv('DB_HOST')
db_port = os.getenv('DB_PORT')
db_name = os.getenv('POSTGRES_DB')
backend_port = os.getenv('DEVELOP_BACKEND_PORT')

DATABASE_URL = f'postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}'


BATCH_SIZE = 50000
COOKIE_EXP_TIME = timedelta(days=7)  # Cookie will expire in 7 days



