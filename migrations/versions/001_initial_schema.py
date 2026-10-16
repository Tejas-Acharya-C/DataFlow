"""Initial DataFlow schema

Revision ID: 001_initial
Revises: 
Create Date: 2026-10-16 16:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. datasets
    op.create_table(
        'datasets',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_datasets_name', 'datasets', ['name'])
    op.create_index('ix_datasets_is_deleted', 'datasets', ['is_deleted'])

    # 2. dataset_versions
    op.create_table(
        'dataset_versions',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('dataset_id', sa.String(length=36), sa.ForeignKey('datasets.id', ondelete='CASCADE'), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('storage_path', sa.String(length=1024), nullable=False),
        sa.Column('original_filename', sa.String(length=255), nullable=False),
        sa.Column('file_size_bytes', sa.Integer(), nullable=False),
        sa.Column('checksum', sa.String(length=64), nullable=False),
        sa.Column('row_count', sa.Integer(), nullable=False),
        sa.Column('column_count', sa.Integer(), nullable=False),
        sa.Column('schema_json', sa.JSON(), nullable=False),
        sa.Column('parent_version_id', sa.String(length=36), sa.ForeignKey('dataset_versions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('creation_reason', sa.String(length=255), nullable=False, default='initial_upload'),
        sa.Column('transformation_details', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('dataset_id', 'version_number', name='uq_dataset_version_number'),
    )
    op.create_index('ix_dataset_versions_dataset_id', 'dataset_versions', ['dataset_id'])
    op.create_index('ix_dataset_version_checksum', 'dataset_versions', ['checksum'])

    # 3. data_contracts
    op.create_table(
        'data_contracts',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('name', sa.String(length=255), nullable=False, unique=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False, default=1),
        sa.Column('rules_json', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_data_contracts_name', 'data_contracts', ['name'])

    # 4. validation_runs
    op.create_table(
        'validation_runs',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('dataset_id', sa.String(length=36), sa.ForeignKey('datasets.id', ondelete='CASCADE'), nullable=False),
        sa.Column('version_id', sa.String(length=36), sa.ForeignKey('dataset_versions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('contract_id', sa.String(length=36), sa.ForeignKey('data_contracts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('passed_count', sa.Integer(), nullable=False, default=0),
        sa.Column('failed_count', sa.Integer(), nullable=False, default=0),
        sa.Column('results_json', sa.JSON(), nullable=False),
        sa.Column('executed_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_validation_runs_dataset_id', 'validation_runs', ['dataset_id'])
    op.create_index('ix_validation_runs_version_id', 'validation_runs', ['version_id'])
    op.create_index('ix_validation_runs_contract_id', 'validation_runs', ['contract_id'])

    # 5. profiling_results
    op.create_table(
        'profiling_results',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('dataset_id', sa.String(length=36), sa.ForeignKey('datasets.id', ondelete='CASCADE'), nullable=False),
        sa.Column('version_id', sa.String(length=36), sa.ForeignKey('dataset_versions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('summary_json', sa.JSON(), nullable=False),
        sa.Column('columns_json', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_profiling_results_dataset_id', 'profiling_results', ['dataset_id'])
    op.create_index('ix_profiling_results_version_id', 'profiling_results', ['version_id'])

    # 6. quality_results
    op.create_table(
        'quality_results',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('dataset_id', sa.String(length=36), sa.ForeignKey('datasets.id', ondelete='CASCADE'), nullable=False),
        sa.Column('version_id', sa.String(length=36), sa.ForeignKey('dataset_versions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('score', sa.Float(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('summary', sa.String(length=500), nullable=False),
        sa.Column('checks_json', sa.JSON(), nullable=False),
        sa.Column('recommendations_json', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_quality_results_dataset_id', 'quality_results', ['dataset_id'])
    op.create_index('ix_quality_results_version_id', 'quality_results', ['version_id'])

    # 7. processing_jobs
    op.create_table(
        'processing_jobs',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('job_type', sa.String(length=50), nullable=False),
        sa.Column('dataset_id', sa.String(length=36), sa.ForeignKey('datasets.id', ondelete='SET NULL'), nullable=True),
        sa.Column('version_id', sa.String(length=36), sa.ForeignKey('dataset_versions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, default='pending'),
        sa.Column('progress', sa.Integer(), nullable=False, default=0),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_processing_jobs_job_type', 'processing_jobs', ['job_type'])
    op.create_index('ix_processing_jobs_status', 'processing_jobs', ['status'])
    op.create_index('ix_processing_jobs_created_at', 'processing_jobs', ['created_at'])

    # 8. audit_events
    op.create_table(
        'audit_events',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('entity_id', sa.String(length=36), nullable=False),
        sa.Column('dataset_id', sa.String(length=36), nullable=True),
        sa.Column('version_id', sa.String(length=36), nullable=True),
        sa.Column('outcome', sa.String(length=50), nullable=False, default='success'),
        sa.Column('details_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_audit_events_event_type', 'audit_events', ['event_type'])
    op.create_index('ix_audit_events_entity_id', 'audit_events', ['entity_id'])
    op.create_index('ix_audit_events_created_at', 'audit_events', ['created_at'])
    op.create_index('ix_audit_event_type_outcome', 'audit_events', ['event_type', 'outcome'])


def downgrade() -> None:
    op.drop_table('audit_events')
    op.drop_table('processing_jobs')
    op.drop_table('quality_results')
    op.drop_table('profiling_results')
    op.drop_table('validation_runs')
    op.drop_table('data_contracts')
    op.drop_table('dataset_versions')
    op.drop_table('datasets')
