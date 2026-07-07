"""drop the challenge_locations table

Revision ID: e4b8c62f17a9
Revises: c7f3a84e91d2
Create Date: 2026-07-07

The BDC challenge export was reachable only from the retired SPA; its routes
and ops are removed in the same change. Downgrade recreates the table as the
initial migration defined it (data is not restored).
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "e4b8c62f17a9"
down_revision = "c7f3a84e91d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("challenge_locations")


def downgrade() -> None:
    op.create_table(
        "challenge_locations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("address", sa.String(), nullable=True),
        sa.Column("primary_city", sa.String(), nullable=True),
        sa.Column("state", sa.String(), nullable=True),
        sa.Column("zip_code", sa.String(), nullable=True),
        sa.Column("zip_code_suffix", sa.String(), nullable=True),
        sa.Column("unit_count", sa.String(), nullable=True),
        sa.Column("building_type_code", sa.String(), nullable=True),
        sa.Column("non_bsl_code", sa.String(), nullable=True),
        sa.Column("bsl_lacks_address_flag", sa.String(), nullable=True),
        sa.Column("latitude", sa.String(), nullable=True),
        sa.Column("longitude", sa.String(), nullable=True),
        sa.Column("address_id", sa.String(), nullable=True),
        sa.Column("contact_name", sa.String(), nullable=True),
        sa.Column("contact_email", sa.String(), nullable=True),
        sa.Column("contact_phone", sa.String(), nullable=True),
        sa.Column("category_code", sa.String(), nullable=True),
        sa.Column("location_id", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
