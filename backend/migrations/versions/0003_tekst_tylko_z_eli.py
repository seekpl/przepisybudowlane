"""tekst prawa tylko z ELI: wersja tekstu wymaga migawki z sumą SHA-256 (arkusz, działanie 2.1)

Revision ID: 0003
Revises: 0002
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

MANUAL = "SELECT id FROM legal_text_version WHERE snapshot_id IS NULL OR origin <> 'eli'"


def upgrade() -> None:
    # Teksty wpisane ręcznie w prototypie znikają razem z ich brzmieniami jednostek. Objaśnienia zostają —
    # tracą tylko wskazanie brzmienia, na którym je oparto, więc nie dadzą się opublikować bez tekstu z ELI.
    op.execute(
        "UPDATE explanation_version SET based_on_unit_version_id = NULL WHERE based_on_unit_version_id IN "
        f"(SELECT id FROM legal_unit_version WHERE text_version_id IN ({MANUAL}))"
    )
    op.execute(f"DELETE FROM legal_unit_version WHERE text_version_id IN ({MANUAL})")
    op.execute(f"DELETE FROM legal_text_version WHERE id IN ({MANUAL})")
    op.alter_column("legal_text_version", "snapshot_id", nullable=False)
    op.create_check_constraint("ck_text_version_from_eli", "legal_text_version", "origin = 'eli'")
    op.create_check_constraint("ck_snapshot_sha256", "source_snapshot", "sha256 ~ '^[0-9a-f]{64}$'")


def downgrade() -> None:
    op.drop_constraint("ck_snapshot_sha256", "source_snapshot", type_="check")
    op.drop_constraint("ck_text_version_from_eli", "legal_text_version", type_="check")
    op.alter_column("legal_text_version", "snapshot_id", nullable=True)
