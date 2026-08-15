"""initial schema

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-08-15 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table(
        'rules',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('keyword', sa.String(length=255), nullable=False),
        sa.Column('dm_message', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_rules_keyword'), 'rules', ['keyword'], unique=False)

    op.create_table(
        'webhook_events',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('event_id', sa.String(length=255), nullable=False),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('processed', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_webhook_events_event_id'), 'webhook_events', ['event_id'], unique=True)

    op.create_table(
        'user_rule_executions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('rule_id', sa.String(length=36), nullable=False),
        sa.Column('comment_id', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['rule_id'], ['rules.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'rule_id', name='uq_user_rule')
    )
    op.create_index(op.f('ix_user_rule_executions_user_id'), 'user_rule_executions', ['user_id'], unique=False)

    op.create_table(
        'dm_jobs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('rule_id', sa.String(length=36), nullable=False),
        sa.Column('comment_id', sa.String(length=255), nullable=False),
        sa.Column('dm_message', sa.Text(), nullable=False),
        sa.Column('pseudogram_dm_id', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('idempotency_key', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['rule_id'], ['rules.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_dm_jobs_comment_id'), 'dm_jobs', ['comment_id'], unique=False)
    op.create_index(op.f('ix_dm_jobs_idempotency_key'), 'dm_jobs', ['idempotency_key'], unique=True)
    op.create_index(op.f('ix_dm_jobs_pseudogram_dm_id'), 'dm_jobs', ['pseudogram_dm_id'], unique=False)
    op.create_index(op.f('ix_dm_jobs_status'), 'dm_jobs', ['status'], unique=False)
    op.create_index(op.f('ix_dm_jobs_user_id'), 'dm_jobs', ['user_id'], unique=False)

    op.create_table(
        'duplicate_logs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('reason', sa.String(length=100), nullable=False),
        sa.Column('event_id', sa.String(length=255), nullable=True),
        sa.Column('user_id', sa.String(length=255), nullable=True),
        sa.Column('rule_id', sa.String(length=36), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

def downgrade() -> None:
    op.drop_table('duplicate_logs')
    op.drop_index(op.f('ix_dm_jobs_user_id'), table_name='dm_jobs')
    op.drop_index(op.f('ix_dm_jobs_status'), table_name='dm_jobs')
    op.drop_index(op.f('ix_dm_jobs_pseudogram_dm_id'), table_name='dm_jobs')
    op.drop_index(op.f('ix_dm_jobs_idempotency_key'), table_name='dm_jobs')
    op.drop_index(op.f('ix_dm_jobs_comment_id'), table_name='dm_jobs')
    op.drop_table('dm_jobs')
    op.drop_index(op.f('ix_user_rule_executions_user_id'), table_name='user_rule_executions')
    op.drop_table('user_rule_executions')
    op.drop_index(op.f('ix_webhook_events_event_id'), table_name='webhook_events')
    op.drop_table('webhook_events')
    op.drop_index(op.f('ix_rules_keyword'), table_name='rules')
    op.drop_table('rules')
