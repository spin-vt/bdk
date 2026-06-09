"""Alembic migration smoke test.

CI builds the test schema via ``Base.metadata.create_all`` (fast), which leaves
the Alembic migrations themselves unexercised — yet prod's schema is owned by
``alembic upgrade head`` in the container entrypoint. this app adds migrations
(platform-admin columns, ``audit_log``), so this test proves, on a real
Postgres, that:

  1. every migration applies cleanly from an empty DB (``upgrade head``),
  2. the migrated schema matches the ORM models (no model/migration drift —
     catches "added a column to models.py but forgot the migration" and the
     reverse),
  3. every migration has a working ``downgrade`` (``downgrade base``),
  4. the upgrade is repeatable.

DB-bound: skips when the integration Postgres isn't reachable (same policy as
the other DB tests). It performs schema surgery, so it restores the
``create_all`` schema on the way out to leave the rest of the suite unaffected.
"""

import os

import pytest
from sqlalchemy import inspect, text

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _alembic_config():
    from alembic.config import Config

    cfg = Config(os.path.join(BACKEND_DIR, "alembic.ini"))
    # Resolve script_location to an absolute path so the test works regardless
    # of the process's working directory. env.py reads the DB connection from
    # the POSTGRES_*/DB_* env vars (set by conftest), not from the .ini URL.
    cfg.set_main_option("script_location", os.path.join(BACKEND_DIR, "alembic"))
    return cfg


def _drop_everything(engine):
    """Return the database to a blank slate (no ORM tables, no alembic_version)."""
    import database.models  # noqa: F401  registers every table on Base.metadata
    from database.base import Base

    Base.metadata.drop_all(engine)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))


@pytest.mark.usefixtures("_require_db")
def test_migrations_roundtrip_and_match_models():
    import database.models  # noqa: F401
    from alembic import command
    from database.base import Base
    from database.sessions import engine

    cfg = _alembic_config()

    # Exercise the migrations from a guaranteed-empty schema, not whatever
    # create_all may have left behind.
    _drop_everything(engine)
    try:
        # 1) Full upgrade from empty must succeed.
        command.upgrade(cfg, "head")

        # 2) Table-level parity with the models.
        migrated_tables = set(inspect(engine).get_table_names()) - {"alembic_version"}
        model_tables = set(Base.metadata.tables.keys())
        assert migrated_tables == model_tables, (
            f"migration/model table drift: only-in-DB={migrated_tables - model_tables}, "
            f"only-in-models={model_tables - migrated_tables}"
        )

        # 2b) Column-level parity per table (this is what guards the platform-admin
        #     column additions, e.g. user.is_platform_admin).
        insp = inspect(engine)
        for table_name, table in Base.metadata.tables.items():
            db_cols = {c["name"] for c in insp.get_columns(table_name)}
            model_cols = {c.name for c in table.columns}
            assert db_cols == model_cols, (
                f"column drift in {table_name}: only-in-DB={db_cols - model_cols}, "
                f"only-in-models={model_cols - db_cols}"
            )

        # 3) Full downgrade must succeed and leave no ORM tables behind.
        command.downgrade(cfg, "base")
        remaining = set(inspect(engine).get_table_names()) - {"alembic_version"}
        assert not remaining, f"downgrade base left tables behind: {remaining}"

        # 4) Re-upgrade must succeed (repeatable).
        command.upgrade(cfg, "head")
    finally:
        # Restore the create_all schema so other tests (which rely on the
        # _schema/db_session fixtures) are unaffected by our schema surgery.
        _drop_everything(engine)
        Base.metadata.create_all(engine)
