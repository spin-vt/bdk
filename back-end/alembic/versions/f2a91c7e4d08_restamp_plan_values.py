"""Restamp plan values onto files and kml rows (one-time data repair).

Default plans originally did NOT write through — filings whose plans were
saved before that fix still carry the upload's 0/0 placeholder speeds in
their file columns and computed kml rows (which the export reads). Re-derive
both from the governing plans, area-edit plan markers re-applied last, for
every upload filing. Idempotent; plan-less legacy filings are untouched.
Snapshots (export folders) stay frozen by design — regenerate a submission
to get a corrected CSV.

Revision ID: f2a91c7e4d08
Revises: 385ef81c2caa
Create Date: 2026-06-11
"""

from alembic import op
from sqlalchemy.orm import Session

revision = "f2a91c7e4d08"
down_revision = "385ef81c2caa"
branch_labels = None
depends_on = None


def upgrade():
    # A data-only repair using the service layer (valid at this schema point:
    # the models match the migrated tables exactly as of this revision).
    from database.models import folder
    from services import plan_service

    session = Session(bind=op.get_bind())
    for (fid,) in session.query(folder.id).filter(folder.type == "upload").all():
        plan_service.restamp_folder(fid, session)
    session.flush()


def downgrade():
    # Data repair — nothing to undo.
    pass
