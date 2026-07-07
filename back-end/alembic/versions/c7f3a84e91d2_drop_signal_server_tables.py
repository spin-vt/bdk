"""drop the signal-server tables

Revision ID: c7f3a84e91d2
Revises: a9e5d21c7b48
Create Date: 2026-07-07

The signal-server propagation feature (towers, their parameters, and the
rendered coverage rasters) was dead code reachable only from the retired SPA;
the code is removed in the same change. Downgrade recreates the tables as the
initial migration defined them (data is not restored).
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "c7f3a84e91d2"
down_revision = "a9e5d21c7b48"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("towerinfo")
    op.drop_table("rasterdata")
    op.drop_table("tower")


def downgrade() -> None:
    op.create_table(
        "tower",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tower_name", sa.String(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "rasterdata",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("image_data", sa.LargeBinary(), nullable=True),
        sa.Column("transparent_image_data", sa.LargeBinary(), nullable=True),
        sa.Column("loss_color_mapping", sa.JSON(), nullable=True),
        sa.Column("north_bound", sa.String(), nullable=True),
        sa.Column("south_bound", sa.String(), nullable=True),
        sa.Column("east_bound", sa.String(), nullable=True),
        sa.Column("west_bound", sa.String(), nullable=True),
        sa.Column("tower_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["tower_id"], ["tower.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "towerinfo",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("latitude", sa.String(), nullable=True),
        sa.Column("longitude", sa.String(), nullable=True),
        sa.Column("frequency", sa.String(), nullable=True),
        sa.Column("radius", sa.String(), nullable=True),
        sa.Column("antennaHeight", sa.String(), nullable=True),
        sa.Column("antennaTilt", sa.String(), nullable=True),
        sa.Column("horizontalFacing", sa.String(), nullable=True),
        sa.Column("floorLossRate", sa.String(), nullable=True),
        sa.Column("tower_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["tower_id"], ["tower.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
