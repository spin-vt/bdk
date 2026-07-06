"""add used_email_token table

Revision ID: a9e5d21c7b48
Revises: f2a91c7e4d08
Create Date: 2026-07-06

One-time-use ledger for email link tokens (verify / reset / join-org): the
token's jti is recorded on first successful use so replays are refused.
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "a9e5d21c7b48"
down_revision = "f2a91c7e4d08"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "used_email_token",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("jti", sa.String(length=36), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("jti"),
    )
    op.create_index("ix_used_email_token_expires_at", "used_email_token", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_used_email_token_expires_at", table_name="used_email_token")
    op.drop_table("used_email_token")
