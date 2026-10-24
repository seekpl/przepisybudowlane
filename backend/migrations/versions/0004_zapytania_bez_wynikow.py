"""zapytania bez wyników — źródło propozycji synonimów (arkusz, działanie 5.4)

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "search_miss",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("query", sa.String(length=80), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("first_seen_on", sa.Date(), nullable=False),
        sa.Column("last_seen_on", sa.Date(), nullable=False),
        sa.Column("resolved", sa.String(length=20), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("query"),
    )


def downgrade() -> None:
    op.drop_table("search_miss")
