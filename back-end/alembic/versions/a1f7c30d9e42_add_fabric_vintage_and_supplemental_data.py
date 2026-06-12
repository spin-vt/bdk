"""add fabric vintage and supplemental data

Revision ID: a1f7c30d9e42
Revises: 93e47504d74d
Create Date: 2026-06-10 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1f7c30d9e42'
down_revision = '93e47504d74d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('supplemental_data',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('location_id', sa.Integer(), nullable=True),
    sa.Column('address', sa.String(), nullable=True),
    sa.Column('city', sa.String(), nullable=True),
    sa.Column('state', sa.String(), nullable=True),
    sa.Column('zip_code', sa.String(), nullable=True),
    sa.Column('zip_suffix', sa.String(), nullable=True),
    sa.Column('primary_supplemental', sa.String(), nullable=True),
    sa.Column('address_source', sa.String(), nullable=True),
    sa.Column('file_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['file_id'], ['file.id'], name='supplemental_data_file_id_fkey', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_supplemental_data_file_id', 'supplemental_data', ['file_id'], unique=False)
    op.create_index('ix_supplemental_data_location_id', 'supplemental_data', ['location_id'], unique=False)
    op.add_column('file', sa.Column('fabric_data_as_of', sa.Date(), nullable=True))
    op.add_column('file', sa.Column('fabric_release', sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column('file', 'fabric_release')
    op.drop_column('file', 'fabric_data_as_of')
    op.drop_index('ix_supplemental_data_location_id', table_name='supplemental_data')
    op.drop_index('ix_supplemental_data_file_id', table_name='supplemental_data')
    op.drop_table('supplemental_data')
