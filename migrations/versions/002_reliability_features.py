"""Add reliability features: rejections, checkpoints, job attempts and quarantine

Revision ID: 002_reliability
Revises: 001_initial
Create Date: 2026-10-16 18:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '002_reliability'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add reliability columns to processing_jobs
    with op.batch_alter_table('processing_jobs') as batch_op:
        batch_op.add_column(sa.Column('attempts', sa.Integer(), nullable=False, server_default='1'))
        batch_op.add_column(sa.Column('max_attempts', sa.Integer(), nullable=False, server_default='1'))
        batch_op.add_column(sa.Column('error_category', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('duration_ms', sa.Integer(), nullable=True))

    # 2. Add quarantine and row metrics to validation_runs
    with op.batch_alter_table('validation_runs') as batch_op:
        batch_op.add_column(sa.Column('accepted_rows', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('rejected_rows', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('quarantine_path', sa.String(length=1024), nullable=True))
        batch_op.add_column(sa.Column('clean_path', sa.String(length=1024), nullable=True))

    # 3. Create validation_rejections table
    op.create_table(
        'validation_rejections',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('run_id', sa.String(length=36), sa.ForeignKey('validation_runs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('dataset_id', sa.String(length=36), sa.ForeignKey('datasets.id', ondelete='CASCADE'), nullable=False),
        sa.Column('version_id', sa.String(length=36), sa.ForeignKey('dataset_versions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('row_number', sa.Integer(), nullable=False),
        sa.Column('raw_data', sa.JSON(), nullable=False),
        sa.Column('failure_reasons', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_validation_rejections_run_id', 'validation_rejections', ['run_id'])
    op.create_index('ix_validation_rejections_dataset_id', 'validation_rejections', ['dataset_id'])
    op.create_index('ix_validation_rejections_version_id', 'validation_rejections', ['version_id'])
    op.create_index('ix_validation_rejections_row_number', 'validation_rejections', ['row_number'])

    # 4. Create ingestion_checkpoints table
    op.create_table(
        'ingestion_checkpoints',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('source_identifier', sa.String(length=255), nullable=False),
        sa.Column('dataset_id', sa.String(length=36), sa.ForeignKey('datasets.id', ondelete='CASCADE'), nullable=False),
        sa.Column('cursor_column', sa.String(length=100), nullable=False),
        sa.Column('watermark_value', sa.String(length=255), nullable=False),
        sa.Column('records_extracted', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('source_identifier', 'dataset_id', name='uq_source_dataset_checkpoint'),
    )
    op.create_index('ix_ingestion_checkpoints_source_id', 'ingestion_checkpoints', ['source_identifier'])
    op.create_index('ix_ingestion_checkpoints_dataset_id', 'ingestion_checkpoints', ['dataset_id'])


def downgrade() -> None:
    op.drop_table('ingestion_checkpoints')
    op.drop_table('validation_rejections')

    with op.batch_alter_table('validation_runs') as batch_op:
        batch_op.drop_column('clean_path')
        batch_op.drop_column('quarantine_path')
        batch_op.drop_column('rejected_rows')
        batch_op.drop_column('accepted_rows')

    with op.batch_alter_table('processing_jobs') as batch_op:
        batch_op.drop_column('duration_ms')
        batch_op.drop_column('error_category')
        batch_op.drop_column('max_attempts')
        batch_op.drop_column('attempts')
