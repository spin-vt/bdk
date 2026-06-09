"""add platform admin and disabled flags to user

Revision ID: 9a3e1c7b42f0
Revises: 57780bad18dd
Create Date: 2026-06-05

A distinct platform-admin concept (the platform operator) separate from
the existing org-level ``is_admin``, plus a reversible soft-disable flag. Both
NOT NULL with a server_default so existing rows backfill to false.
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "9a3e1c7b42f0"
down_revision = "57780bad18dd"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column(
            "is_platform_admin", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
    )
    op.add_column(
        "user",
        sa.Column("disabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("user", "disabled")
    op.drop_column("user", "is_platform_admin")
