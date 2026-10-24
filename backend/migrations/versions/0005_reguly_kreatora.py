"""reguły kreatora z art. 29 Prawa budowlanego — propozycje i decyzje recenzenta (arkusz, działanie 4.1)

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "wizard_rule",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("act_id", sa.Integer(), nullable=False),
        sa.Column("text_version_id", sa.Integer(), nullable=False),
        sa.Column("unit_id", sa.Integer(), nullable=False),
        sa.Column("unit_key", sa.String(length=80), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("requirement", sa.String(length=20), nullable=False),
        sa.Column("object_text", sa.Text(), nullable=False),
        sa.Column("conditions", postgresql.JSONB(), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("reviewed_by", sa.String(length=120), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["act_id"], ["legal_act.id"]),
        sa.ForeignKeyConstraint(["text_version_id"], ["legal_text_version.id"]),
        sa.ForeignKeyConstraint(["unit_id"], ["legal_unit.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("text_version_id", "unit_key", name="uq_wizard_rule_unit"),
    )


def downgrade() -> None:
    op.drop_table("wizard_rule")
