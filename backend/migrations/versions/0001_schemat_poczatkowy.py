"""schemat poczatkowy

Revision ID: 0001
Revises: —
Create Date: 2026-10-20 08:42:15.570670
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "content_flag",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("entity", sa.String(length=60), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(length=120), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.String(length=120), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_flag_entity", "content_flag", ["entity", "entity_id"], unique=False)
    op.create_table(
        "decision_tree",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "editorial_event",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("entity", sa.String(length=60), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("from_state", sa.String(length=20), nullable=True),
        sa.Column("to_state", sa.String(length=20), nullable=False),
        sa.Column("actor", sa.String(length=120), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_editorial_event_entity", "editorial_event", ["entity", "entity_id"], unique=False)
    op.create_table(
        "glossary_term",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "guide",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "legal_act",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("eli", sa.String(length=40), nullable=False),
        sa.Column("short_title", sa.String(length=200), nullable=False),
        sa.Column("abbrev", sa.String(length=20), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("citation_name", sa.Text(), nullable=False),
        sa.Column("act_kind", sa.String(length=40), nullable=False),
        sa.Column("area", sa.String(length=80), nullable=False),
        sa.Column("in_mvp", sa.Boolean(), nullable=False),
        sa.Column("official_url", sa.Text(), nullable=False),
        sa.Column("text_format", sa.String(length=20), nullable=False),
        sa.Column("owner", sa.String(length=120), nullable=True),
        sa.Column("manifest_verified_on", sa.Date(), nullable=True),
        sa.Column("relations", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("eli"),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "search_document",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("ref", sa.String(length=160), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("subtitle", sa.Text(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("tsv", postgresql.TSVECTOR(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("kind", "ref", name="uq_search_doc"),
    )
    op.create_index("ix_search_tsv", "search_document", ["tsv"], unique=False, postgresql_using="gin")
    op.create_table(
        "search_synonym",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("term", sa.String(length=80), nullable=False),
        sa.Column("expansions", postgresql.JSONB(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("term"),
    )
    op.create_table(
        "sync_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("trigger", sa.String(length=40), nullable=False),
        sa.Column("since", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stats", postgresql.JSONB(), nullable=False),
        sa.Column("errors", postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "system_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor", sa.String(length=120), nullable=False),
        sa.Column("entity", sa.String(length=60), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=60), nullable=False),
        sa.Column("data", postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_history_entity", "system_history", ["entity", "entity_id"], unique=False)
    op.create_table(
        "decision_tree_version",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tree_id", sa.Integer(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("intro", sa.Text(), nullable=True),
        sa.Column("scope_note", sa.Text(), nullable=True),
        sa.Column("root_node_key", sa.String(length=60), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("author", sa.String(length=120), nullable=False),
        sa.Column("reviewer", sa.String(length=120), nullable=True),
        sa.Column("verified_on", sa.Date(), nullable=True),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["tree_id"],
            ["decision_tree.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tree_id", "version_no", name="uq_tree_version"),
    )
    op.create_table(
        "glossary_term_version",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("term_id", sa.Integer(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("term_label", sa.String(length=120), nullable=False),
        sa.Column("definition", sa.Text(), nullable=False),
        sa.Column("basis_label", sa.Text(), nullable=True),
        sa.Column("unit_slugs", postgresql.JSONB(), nullable=False),
        sa.Column("see_also", postgresql.JSONB(), nullable=False),
        sa.Column("illustration", sa.String(length=80), nullable=True),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("author", sa.String(length=120), nullable=False),
        sa.Column("reviewer", sa.String(length=120), nullable=True),
        sa.Column("verified_on", sa.Date(), nullable=True),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["term_id"],
            ["glossary_term.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("term_id", "version_no", name="uq_term_version"),
    )
    op.create_table(
        "guide_version",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("guide_id", sa.Integer(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("caveat", sa.Text(), nullable=True),
        sa.Column("steps", postgresql.JSONB(), nullable=False),
        sa.Column("unit_slugs", postgresql.JSONB(), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("author", sa.String(length=120), nullable=False),
        sa.Column("reviewer", sa.String(length=120), nullable=True),
        sa.Column("verified_on", sa.Date(), nullable=True),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["guide_id"],
            ["guide.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("guide_id", "version_no", name="uq_guide_version"),
    )
    op.create_table(
        "legal_unit",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("act_id", sa.Integer(), nullable=False),
        sa.Column("unit_key", sa.String(length=120), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("featured", sa.Boolean(), nullable=False),
        sa.Column("illustration", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["act_id"],
            ["legal_act.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("act_id", "unit_key", name="uq_unit_key"),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "source_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("act_id", sa.Integer(), nullable=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("parser_version", sa.String(length=40), nullable=True),
        sa.Column("first_fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["act_id"],
            ["legal_act.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("url", "sha256", name="uq_snapshot_url_sha"),
    )
    op.create_table(
        "sync_checkpoint",
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["sync_run.id"],
        ),
        sa.PrimaryKeyConstraint("source"),
    )
    op.create_table(
        "decision_tree_node_version",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tree_version_id", sa.Integer(), nullable=False),
        sa.Column("node_key", sa.String(length=60), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("step_label", sa.String(length=80), nullable=False),
        sa.Column("question", sa.Text(), nullable=True),
        sa.Column("help", sa.Text(), nullable=True),
        sa.Column("options", postgresql.JSONB(), nullable=False),
        sa.Column("result_title", sa.Text(), nullable=True),
        sa.Column("result_body", sa.Text(), nullable=True),
        sa.Column("outcome", sa.String(length=30), nullable=True),
        sa.Column("basis_label", sa.Text(), nullable=True),
        sa.Column("unit_slugs", postgresql.JSONB(), nullable=False),
        sa.Column("links", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(
            ["tree_version_id"],
            ["decision_tree_version.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tree_version_id", "node_key", name="uq_tree_node"),
    )
    op.create_table(
        "detected_amendment",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("act_id", sa.Integer(), nullable=False),
        sa.Column("amending_eli", sa.String(length=40), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("journal_display", sa.String(length=200), nullable=False),
        sa.Column("published_on", sa.Date(), nullable=True),
        sa.Column("entry_into_force", sa.Date(), nullable=True),
        sa.Column("snapshot_id", sa.Integer(), nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["act_id"],
            ["legal_act.id"],
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["source_snapshot.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("act_id", "amending_eli", name="uq_amendment"),
    )
    op.create_table(
        "editorial_task",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("details", postgresql.JSONB(), nullable=False),
        sa.Column("act_id", sa.Integer(), nullable=True),
        sa.Column("unit_id", sa.Integer(), nullable=True),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("dedupe_key", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_on", sa.Date(), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_by", sa.String(length=120), nullable=True),
        sa.Column("resolution", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["act_id"],
            ["legal_act.id"],
        ),
        sa.ForeignKeyConstraint(
            ["unit_id"],
            ["legal_unit.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedupe_key"),
    )
    op.create_table(
        "explanation",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("unit_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["unit_id"],
            ["legal_unit.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("unit_id"),
    )
    op.create_table(
        "legal_text_version",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("act_id", sa.Integer(), nullable=False),
        sa.Column("text_type", sa.String(length=20), nullable=False),
        sa.Column("source_eli", sa.String(length=40), nullable=True),
        sa.Column("journal_display", sa.String(length=200), nullable=False),
        sa.Column("legal_status_date", sa.Date(), nullable=True),
        sa.Column("published_on", sa.Date(), nullable=True),
        sa.Column("incorporated", postgresql.JSONB(), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=True),
        sa.Column("origin", sa.String(length=20), nullable=False),
        sa.Column("parser_version", sa.String(length=40), nullable=True),
        sa.Column("parse_quality", sa.Float(), nullable=True),
        sa.Column("review_state", sa.String(length=20), nullable=False),
        sa.Column("reviewed_by", sa.String(length=120), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["act_id"],
            ["legal_act.id"],
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["source_snapshot.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("act_id", "snapshot_id", name="uq_text_version_snapshot"),
    )
    op.create_table(
        "legal_validity_interval",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("act_id", sa.Integer(), nullable=False),
        sa.Column("unit_id", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("basis", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("supersedes_id", sa.Integer(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_by", sa.String(length=120), nullable=False),
        sa.ForeignKeyConstraint(
            ["act_id"],
            ["legal_act.id"],
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_id"],
            ["legal_validity_interval.id"],
        ),
        sa.ForeignKeyConstraint(
            ["unit_id"],
            ["legal_unit.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "source_fetch",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sync_run_id", sa.Integer(), nullable=True),
        sa.Column("act_id", sa.Integer(), nullable=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("snapshot_id", sa.Integer(), nullable=True),
        sa.Column("ok", sa.Boolean(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["act_id"],
            ["legal_act.id"],
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["source_snapshot.id"],
        ),
        sa.ForeignKeyConstraint(
            ["sync_run_id"],
            ["sync_run.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fetch_act_ok", "source_fetch", ["act_id", "ok", "fetched_at"], unique=False)
    op.create_table(
        "source_verification",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("act_id", sa.Integer(), nullable=False),
        sa.Column("unit_id", sa.Integer(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_by", sa.String(length=120), nullable=False),
        sa.Column("method", sa.Text(), nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["act_id"],
            ["legal_act.id"],
        ),
        sa.ForeignKeyConstraint(
            ["unit_id"],
            ["legal_unit.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "error_report",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("target_path", sa.Text(), nullable=False),
        sa.Column("target_label", sa.Text(), nullable=True),
        sa.Column("unit_id", sa.Integer(), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("contact_email", sa.String(length=254), nullable=True),
        sa.Column("consent", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_on", sa.Date(), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("email_purge_after", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["editorial_task.id"],
        ),
        sa.ForeignKeyConstraint(
            ["unit_id"],
            ["legal_unit.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "legal_unit_version",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("unit_id", sa.Integer(), nullable=False),
        sa.Column("text_version_id", sa.Integer(), nullable=False),
        sa.Column("content", postgresql.JSONB(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["text_version_id"],
            ["legal_text_version.id"],
        ),
        sa.ForeignKeyConstraint(
            ["unit_id"],
            ["legal_unit.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("unit_id", "text_version_id", name="uq_unit_in_text"),
    )
    op.create_table(
        "explanation_version",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("explanation_id", sa.Integer(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("based_on_unit_version_id", sa.Integer(), nullable=True),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("author", sa.String(length=120), nullable=False),
        sa.Column("reviewer", sa.String(length=120), nullable=True),
        sa.Column("verified_on", sa.Date(), nullable=True),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["based_on_unit_version_id"],
            ["legal_unit_version.id"],
        ),
        sa.ForeignKeyConstraint(
            ["explanation_id"],
            ["explanation.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("explanation_id", "version_no", name="uq_explanation_version"),
    )


def downgrade() -> None:
    op.drop_table("explanation_version")
    op.drop_table("legal_unit_version")
    op.drop_table("error_report")
    op.drop_table("source_verification")
    op.drop_index("ix_fetch_act_ok", table_name="source_fetch")
    op.drop_table("source_fetch")
    op.drop_table("legal_validity_interval")
    op.drop_table("legal_text_version")
    op.drop_table("explanation")
    op.drop_table("editorial_task")
    op.drop_table("detected_amendment")
    op.drop_table("decision_tree_node_version")
    op.drop_table("sync_checkpoint")
    op.drop_table("source_snapshot")
    op.drop_table("legal_unit")
    op.drop_table("guide_version")
    op.drop_table("glossary_term_version")
    op.drop_table("decision_tree_version")
    op.drop_index("ix_history_entity", table_name="system_history")
    op.drop_table("system_history")
    op.drop_table("sync_run")
    op.drop_table("search_synonym")
    op.drop_index("ix_search_tsv", table_name="search_document", postgresql_using="gin")
    op.drop_table("search_document")
    op.drop_table("legal_act")
    op.drop_table("guide")
    op.drop_table("glossary_term")
    op.drop_index("ix_editorial_event_entity", table_name="editorial_event")
    op.drop_table("editorial_event")
    op.drop_table("decision_tree")
    op.drop_index("ix_flag_entity", table_name="content_flag")
    op.drop_table("content_flag")
