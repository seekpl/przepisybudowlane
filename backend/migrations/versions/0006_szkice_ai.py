"""szkice objaśnień AI: model, zdania z cytatami, raport walidatorów (arkusz, działania 3.3–3.6)

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("explanation_version", sa.Column("ai_model", sa.String(length=80), nullable=True))
    op.add_column("explanation_version", sa.Column("ai_sentences", postgresql.JSONB(), nullable=True))
    op.add_column("explanation_version", sa.Column("ai_report", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("explanation_version", "ai_report")
    op.drop_column("explanation_version", "ai_sentences")
    op.drop_column("explanation_version", "ai_model")
