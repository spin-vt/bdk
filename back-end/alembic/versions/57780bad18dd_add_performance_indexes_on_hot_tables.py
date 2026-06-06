"""add performance indexes on hot tables

Revision ID: 57780bad18dd
Revises: 7955e39062da
Create Date: 2026-06-05 15:07:02.972682

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '57780bad18dd'
down_revision = '7955e39062da'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Hot-path indexes (see database.models __table_args__ — kept in sync).
    # Coverage reads/writes filter kml_data & fabric_data by file_id/location_id;
    # tile serving looks up vector_tiles by (mbtiles_id, zoom, column, row); the
    # task list filters celerytaskinfo by organization_id.
    op.create_index("ix_kml_data_file_id", "kml_data", ["file_id"])
    op.create_index("ix_kml_data_location_id", "kml_data", ["location_id"])
    op.create_index("ix_fabric_data_file_id", "fabric_data", ["file_id"])
    op.create_index("ix_fabric_data_location_id", "fabric_data", ["location_id"])
    op.create_index(
        "ix_celerytaskinfo_organization_id", "celerytaskinfo", ["organization_id"]
    )
    op.create_index(
        "ix_vector_tiles_lookup",
        "vector_tiles",
        ["mbtiles_id", "zoom_level", "tile_column", "tile_row"],
    )


def downgrade() -> None:
    op.drop_index("ix_vector_tiles_lookup", table_name="vector_tiles")
    op.drop_index("ix_celerytaskinfo_organization_id", table_name="celerytaskinfo")
    op.drop_index("ix_fabric_data_location_id", table_name="fabric_data")
    op.drop_index("ix_fabric_data_file_id", table_name="fabric_data")
    op.drop_index("ix_kml_data_location_id", table_name="kml_data")
    op.drop_index("ix_kml_data_file_id", table_name="kml_data")
