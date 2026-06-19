"""panel admin: audit log y system settings

Revision ID: 22d436dd1c32
Revises: 209e766ea6ec
Create Date: 2026-05-03 03:50:38.078514+00:00

Crea las tablas que dan soporte al panel administrativo:

- admin_audit_log : bitácora append-only de acciones privilegiadas.
- system_settings : configuración runtime modificable por admin (toggles).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '22d436dd1c32'
down_revision: Union[str, Sequence[str], None] = '209e766ea6ec'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'admin_audit_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('actor_id', sa.Integer(), nullable=True),
        sa.Column('actor_username', sa.String(length=64), nullable=True),
        sa.Column('action', sa.String(length=64), nullable=False),
        sa.Column('entity_type', sa.String(length=64), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=True),
        sa.Column('before', sa.JSON(), nullable=True),
        sa.Column('after', sa.JSON(), nullable=True),
        sa.Column('extra', sa.JSON(), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_admin_audit_log_action'), 'admin_audit_log', ['action'], unique=False
    )
    op.create_index(
        op.f('ix_admin_audit_log_actor_id'),
        'admin_audit_log',
        ['actor_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_admin_audit_log_created_at'),
        'admin_audit_log',
        ['created_at'],
        unique=False,
    )
    op.create_index(
        op.f('ix_admin_audit_log_entity_id'),
        'admin_audit_log',
        ['entity_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_admin_audit_log_entity_type'),
        'admin_audit_log',
        ['entity_type'],
        unique=False,
    )

    op.create_table(
        'system_settings',
        sa.Column('key', sa.String(length=64), nullable=False),
        sa.Column('value', sa.JSON(), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('updated_by_id', sa.Integer(), nullable=True),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['updated_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('key'),
    )


def downgrade() -> None:
    op.drop_table('system_settings')
    op.drop_index(op.f('ix_admin_audit_log_entity_type'), table_name='admin_audit_log')
    op.drop_index(op.f('ix_admin_audit_log_entity_id'), table_name='admin_audit_log')
    op.drop_index(op.f('ix_admin_audit_log_created_at'), table_name='admin_audit_log')
    op.drop_index(op.f('ix_admin_audit_log_actor_id'), table_name='admin_audit_log')
    op.drop_index(op.f('ix_admin_audit_log_action'), table_name='admin_audit_log')
    op.drop_table('admin_audit_log')
