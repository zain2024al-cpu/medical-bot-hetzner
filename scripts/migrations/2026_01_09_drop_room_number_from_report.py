"""
Migration script to drop the 'room_number' column from the 'report' table.
"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.drop_column('report', 'room_number')

def downgrade():
    op.add_column('report', sa.Column('room_number', sa.String(length=100), nullable=True))
