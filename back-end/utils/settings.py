import os
from datetime import timedelta
from urllib.parse import quote_plus

# Parse as a real boolean: the raw env value is a string, and a non-empty string
# like "0" is truthy in Python — so `os.getenv("IN_PRODUCTION")` made the dev
# value IN_PRODUCTION=0 read as True (and set Secure cookies in dev). Treat only
# explicit truthy strings as production. (prod sets "1", test "", dev "0".)
IN_PRODUCTION = os.getenv("IN_PRODUCTION", "").strip().lower() in ("1", "true", "yes", "on")

# For production
db_user = os.getenv("POSTGRES_USER")
db_password = quote_plus(os.getenv("POSTGRES_PASSWORD"))
db_host = os.getenv("DB_HOST")
db_port = os.getenv("DB_PORT")
db_name = os.getenv("POSTGRES_DB")
backend_port = os.getenv("DEVELOP_BACKEND_PORT")

DATABASE_URL = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"


BATCH_SIZE = 50000
COOKIE_EXP_TIME = timedelta(days=7)  # Cookie will expire in 7 days
