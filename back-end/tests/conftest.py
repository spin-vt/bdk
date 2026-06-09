"""Shared test setup.

`utils.settings` / `utils.config` read environment variables at import time
(e.g. `quote_plus(os.getenv('POSTGRES_PASSWORD'))`), so any import of the
controller modules fails without them. Set harmless dummies before the app
package is imported. These never connect anywhere — engines are created lazily
and these unit tests don't touch a real database.
"""

import os

# Test-environment defaults, set with setdefault so the docker-compose `test`
# service (which provides DB_HOST=test-db etc. as real env vars) wins, while
# local bare-metal runs fall back to a throwaway Postgres on localhost:5433.
# settings.py builds DATABASE_URL and Celery reads its transports at IMPORT
# time, so these must be set before any app/controller import below.
_DEFAULTS = {
    "POSTGRES_USER": "test",
    "POSTGRES_PASSWORD": "test",
    "POSTGRES_DB": "bdk_test",
    "DB_HOST": "localhost",
    "DB_PORT": "5433",
    "DEVELOP_BACKEND_PORT": "8000",
    "IN_PRODUCTION": "",
    "SECRET_KEY": "test-secret",
    "JWT_SECRET": "test-jwt-secret",
    "JWT_TOKEN_LOCATION": "cookies",
    "JWT_ACCESS_COOKIE_NAME": "token",
    "MAIL_USE_TLS": "false",
    "MAIL_USE_SSL": "false",
    # In-memory Celery transports so eager tasks never reach for Redis.
    "CELERY_BROKER_URL": "memory://",
    "CELERY_RESULT_BACKEND": "cache+memory://",
    # Rate limiting off by default in tests (in-memory limiter storage is
    # process-global and would leak counts across tests); the dedicated
    # rate-limit test flips it on locally.
    "RATELIMIT_ENABLED": "false",
}
for _k, _v in _DEFAULTS.items():
    os.environ.setdefault(_k, _v)

import pytest  # noqa: E402

# Repo paths -----------------------------------------------------------------
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(BACKEND_DIR)
SYNTHETIC_DIR = os.path.join(REPO_ROOT, "dev-data", "synthetic")
REAL_DIR = os.path.join(REPO_ROOT, "dev-data", "real-do-not-commit")


def _db_reachable():
    """True if the integration Postgres is up; used to skip DB-bound modules."""
    import sqlalchemy
    from sqlalchemy.exc import OperationalError

    from utils.settings import DATABASE_URL

    try:
        eng = sqlalchemy.create_engine(DATABASE_URL)
        with eng.connect():
            pass
        eng.dispose()
        return True
    except OperationalError:
        return False


@pytest.fixture(scope="session")
def _require_db():
    if not _db_reachable():
        pytest.skip("integration Postgres not reachable on localhost:5433")


@pytest.fixture(scope="session", autouse=False)
def _schema(_require_db):
    """Create all tables once for the test session."""
    import database.models  # noqa: F401  (registers all tables on Base.metadata)
    from database.base import Base
    from database.sessions import engine

    Base.metadata.create_all(engine)
    return engine


@pytest.fixture()
def db_session(_schema):
    """A clean Session per test. TRUNCATEs every table before yielding so tests
    are isolated regardless of order."""
    from sqlalchemy import text

    from database.base import Base
    from database.sessions import Session

    session = Session()
    table_names = ", ".join(f'"{t.name}"' for t in reversed(Base.metadata.sorted_tables))
    session.execute(text(f"TRUNCATE {table_names} RESTART IDENTITY CASCADE;"))
    session.commit()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(autouse=True)
def _eager_celery():
    """Run Celery tasks inline (no Redis broker) for any test that triggers
    .apply_async(). Test-only config; app code is untouched."""
    try:
        from controllers.celery_controller.celery_config import celery
    except Exception:
        yield
        return
    prev_eager = celery.conf.task_always_eager
    prev_prop = celery.conf.task_eager_propagates
    prev_store = celery.conf.task_store_eager_result
    celery.conf.task_always_eager = True
    celery.conf.task_eager_propagates = True
    celery.conf.task_store_eager_result = True
    try:
        yield
    finally:
        celery.conf.task_always_eager = prev_eager
        celery.conf.task_eager_propagates = prev_prop
        celery.conf.task_store_eager_result = prev_store


# A tiny KML with two <Folder>s (one holding both a Point and a LineString).
# GDAL/LIBKML exposes folders as separate layers, so a correct reader must
# concatenate them: 3 geometries total (2 LineString, 1 Point).
SAMPLE_KML = b"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Folder><name>A</name>
      <Placemark><name>line A</name>
        <LineString><coordinates>-116.80,46.40,0 -116.70,46.45,0</coordinates></LineString>
      </Placemark>
    </Folder>
    <Folder><name>B</name>
      <Placemark><name>cabinet</name>
        <Point><coordinates>-116.75,46.42,0</coordinates></Point>
      </Placemark>
      <Placemark><name>line B</name>
        <LineString><coordinates>-116.60,46.50,0 -116.50,46.55,0</coordinates></LineString>
      </Placemark>
    </Folder>
  </Document>
</kml>
"""

# A GeoJSON FeatureCollection with one Polygon and one Point.
SAMPLE_GEOJSON = b"""{
  "type": "FeatureCollection",
  "features": [
    {"type": "Feature", "properties": {},
     "geometry": {"type": "Polygon", "coordinates":
        [[[-116.80,46.40],[-116.70,46.40],[-116.70,46.50],[-116.80,46.50],[-116.80,46.40]]]}},
    {"type": "Feature", "properties": {},
     "geometry": {"type": "Point", "coordinates": [-116.75,46.45]}}
  ]
}"""
