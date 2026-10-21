"""alarm zrodla

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-21 10:25:48.608733
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "source_alarm",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("details", postgresql.JSONB(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=True),
        sa.Column("raised_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.String(length=120), nullable=True),
        sa.Column("resolution", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["sync_run.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_alarm_open", "source_alarm", ["source", "resolved_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_alarm_open", table_name="source_alarm")
    op.drop_table("source_alarm")
