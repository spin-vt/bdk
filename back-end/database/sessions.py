from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import scoped_session, sessionmaker

from database.base import Base
from utils.settings import DATABASE_URL

engine = create_engine(DATABASE_URL)

session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
ScopedSession = scoped_session(session_factory)
Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_session():
    """Request-scoped session for web handlers.

    Returns the same session throughout a single request; its lifecycle
    (rollback of anything uncommitted + close) is handled automatically by the
    ``teardown_appcontext`` registered in ``utils.flask_app``. Handlers must NOT
    call ``.close()`` on it — just ``.commit()`` when they mean to persist.

    NOT for Celery tasks: those run without a Flask app context and manage their
    own ``Session()`` instances (see ``celery_tasks``).
    """
    return ScopedSession()


def init_db():
    """Create tables if the schema isn't present yet.

    Call this at app/worker startup — NOT at import time. Importing a module
    must never require a live database (it broke tests and any offline use).
    Schema is normally managed by Alembic (``alembic upgrade head`` in the
    container entrypoint); this is a fallback for fresh local databases.
    """
    inspector = inspect(engine)
    # Sentinel must be a table that actually exists in any initialized BDK
    # database. The old check used "fabric" (no such table -- it's fabric_data),
    # so create_all ran on EVERY boot and silently created new model tables
    # before their migrations existed.
    if not inspector.has_table("organization"):
        Base.metadata.create_all(engine)
