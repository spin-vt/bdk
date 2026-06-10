"""add markers to editfile

Persist an edit's exact per-point picks alongside its polygon so recomputes
can re-apply the edit exactly instead of geometrically (polygon ∩ linked
coverage files). NULL means a pre-existing editfile; those keep the geometric
re-apply behavior.

Revision ID: b7c4a9e2d5f1
Revises: c4d2e8f1a6b3
Create Date: 2026-06-09
"""

import sqlalchemy as sa
from alembic import op

revision = "b7c4a9e2d5f1"
down_revision = "c4d2e8f1a6b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("editfile", sa.Column("markers", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("editfile", "markers")
