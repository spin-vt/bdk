from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import scoped_session, sessionmaker

from database.base import Base
from utils.settings import DATABASE_URL

engine = create_engine(DATABASE_URL)

session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
ScopedSession = scoped_session(session_factory)
Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Create tables if the schema isn't present yet.

    Call this at app/worker startup — NOT at import time. Importing a module
    must never require a live database (it broke tests and any offline use).
    Schema is normally managed by Alembic (``alembic upgrade head`` in the
    container entrypoint); this is a fallback for fresh local databases.
    """
    inspector = inspect(engine)
    if not inspector.has_table("fabric"):
        Base.metadata.create_all(engine)
