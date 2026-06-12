"""Guard: the performance indexes on the hot tables must stay declared
on the ORM models. These columns drive the per-file coverage reads, tile
lookups, and task listing; losing an index silently regresses query performance
on large data, so we pin the index set.

We assert against ``Base.metadata`` (the source of truth that both
``create_all`` and the alembic migration derive from) rather than a live DB:
that's deterministic and independent of any pre-existing/stale test schema. The
migration that materialises these on existing databases
(``..._add_performance_indexes_on_hot_tables``) was validated separately by an
upgrade/downgrade round-trip.
"""

import database.models  # noqa: F401  (registers all tables on Base.metadata)
from database.base import Base

# table -> set of expected index key-column tuples (order matters for composite)
EXPECTED_INDEXES = {
    "kml_data": {("file_id",), ("location_id",)},
    "fabric_data": {("file_id",), ("location_id",)},
    "supplemental_data": {("file_id",), ("location_id",)},
    "celerytaskinfo": {("organization_id",)},
    "vector_tiles": {("mbtiles_id", "zoom_level", "tile_column", "tile_row")},
}


def test_hot_table_indexes_declared_on_models():
    """Every expected (table, column-tuple) index is declared on the model."""
    missing = []
    for table, expected in EXPECTED_INDEXES.items():
        tbl = Base.metadata.tables[table]
        present = {tuple(c.name for c in ix.columns) for ix in tbl.indexes}
        for cols in expected:
            if cols not in present:
                missing.append(f"{table}{cols} (have: {sorted(present)})")
    assert not missing, "missing indexes:\n  " + "\n  ".join(missing)
