"""esquema inicial

Revision ID: 731810543001
Revises:
Create Date: 2026-11-12 05:27:05.957146
"""

from __future__ import annotations

from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry
from sqlalchemy.dialects import postgresql

revision: str = "731810543001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE SEQUENCE IF NOT EXISTS alert_number_seq START 1")
    postgresql.ENUM("admin", "analyst", "observer", name="user_role").create(bind, checkfirst=True)
    postgresql.ENUM("csv", "pdf", name="report_format").create(bind, checkfirst=True)
    postgresql.ENUM("low", "moderate", "high", "priority", name="severity").create(bind, checkfirst=True)
    postgresql.ENUM("immediate", "daily", "weekly", name="notification_frequency").create(bind, checkfirst=True)
    postgresql.ENUM("queued", "running", "succeeded", "failed", "cancelled", name="job_status").create(bind, checkfirst=True)
    postgresql.ENUM("vegetation_loss", "possible_burn", "possible_flooding", name="change_signal").create(bind, checkfirst=True)
    postgresql.ENUM("new", "pending_review", "in_review", "confirmed", "dismissed", "closed", name="alert_status").create(
        bind, checkfirst=True
    )
    postgresql.ENUM("created", "redetected", "status_changed", "comment", "notified", name="alert_event_type").create(bind, checkfirst=True)
    postgresql.ENUM("alert", "digest", "report", "password_reset", name="notification_kind").create(bind, checkfirst=True)
    postgresql.ENUM("pending", "sent", "failed", "skipped", name="notification_status").create(bind, checkfirst=True)
    # ### comandos autogenerados por Alembic - ¡revísenlos! ###
    op.create_table(
        "model_versions",
        sa.Column("detector_id", sa.String(length=64), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("parameters", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("artifact_uri", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("kind IN ('rule-based', 'deep-learning')", name=op.f("ck_model_versions_kind_values")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_model_versions")),
        sa.UniqueConstraint("detector_id", "version", name="uq_model_version"),
    )
    op.create_table(
        "satellite_sources",
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("provider", sa.String(length=120), nullable=False),
        sa.Column("collection", sa.String(length=120), nullable=False),
        sa.Column("catalog_url", sa.String(length=255), nullable=False),
        sa.Column("license", sa.String(length=255), nullable=False),
        sa.Column("requires_credentials", sa.Boolean(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_satellite_sources")),
        sa.UniqueConstraint("slug", name=op.f("uq_satellite_sources_slug")),
    )
    op.create_geospatial_table(
        "territories",
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "geom",
            Geometry(
                geometry_type="MULTIPOLYGON",
                srid=4326,
                dimension=2,
                spatial_index=False,
                from_text="ST_GeomFromEWKT",
                name="geometry",
                nullable=False,
            ),
            nullable=False,
        ),
        sa.Column("area_km2", sa.Float(), nullable=False),
        sa.Column("source", sa.String(length=255), nullable=False),
        sa.Column("license", sa.String(length=64), nullable=False),
        sa.Column("attribution", sa.String(length=255), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_territories")),
        sa.UniqueConstraint("slug", name=op.f("uq_territories_slug")),
    )
    op.create_geospatial_index("idx_territories_geom", "territories", ["geom"], unique=False, postgresql_using="gist", postgresql_ops={})
    op.create_table(
        "users",
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("full_name", sa.String(length=120), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", postgresql.ENUM(name="user_role", create_type=False), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("failed_login_count", sa.Integer(), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("privacy_accepted_version", sa.String(length=32), nullable=True),
        sa.Column("privacy_accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_index("uq_users_email_lower", "users", [sa.literal_column("lower(email)")], unique=True)
    op.create_table(
        "audit_logs",
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=True),
        sa.Column("resource_id", sa.String(length=64), nullable=True),
        sa.Column("ip_hash", sa.String(length=32), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], name=op.f("fk_audit_logs_actor_id_users"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_logs")),
    )
    op.create_index(op.f("ix_audit_logs_action"), "audit_logs", ["action"], unique=False)
    op.create_index(op.f("ix_audit_logs_actor_id"), "audit_logs", ["actor_id"], unique=False)
    op.create_index(op.f("ix_audit_logs_created_at"), "audit_logs", ["created_at"], unique=False)
    op.create_table(
        "auth_sessions",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("refresh_token_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_token_hash", sa.String(length=64), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip_hash", sa.String(length=32), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_auth_sessions_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_sessions")),
        sa.UniqueConstraint("refresh_token_hash", name=op.f("uq_auth_sessions_refresh_token_hash")),
    )
    op.create_index(op.f("ix_auth_sessions_previous_token_hash"), "auth_sessions", ["previous_token_hash"], unique=False)
    op.create_index(op.f("ix_auth_sessions_user_id"), "auth_sessions", ["user_id"], unique=False)
    op.create_table(
        "cookie_consents",
        sa.Column("subject_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("necessary", sa.Boolean(), nullable=False),
        sa.Column("functional", sa.Boolean(), nullable=False),
        sa.Column("analytics", sa.Boolean(), nullable=False),
        sa.Column("policy_version", sa.String(length=32), nullable=False),
        sa.Column("ip_hash", sa.String(length=32), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_cookie_consents_user_id_users"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cookie_consents")),
    )
    op.create_index(op.f("ix_cookie_consents_subject_id"), "cookie_consents", ["subject_id"], unique=False)
    op.create_geospatial_table(
        "monitored_regions",
        sa.Column("territory_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "geom",
            Geometry(
                geometry_type="MULTIPOLYGON",
                srid=4326,
                dimension=2,
                spatial_index=False,
                from_text="ST_GeomFromEWKT",
                name="geometry",
                nullable=False,
            ),
            nullable=False,
        ),
        sa.Column("area_km2", sa.Float(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("cadence_days", sa.Integer(), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("area_km2 > 0", name=op.f("ck_monitored_regions_area_positive")),
        sa.CheckConstraint("cadence_days BETWEEN 5 AND 365", name=op.f("ck_monitored_regions_cadence_range")),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["users.id"], name=op.f("fk_monitored_regions_created_by_id_users"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["territory_id"], ["territories.id"], name=op.f("fk_monitored_regions_territory_id_territories"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_monitored_regions")),
        sa.UniqueConstraint("territory_id", "name", name="uq_region_name_per_territory"),
    )
    op.create_geospatial_index(
        "idx_monitored_regions_geom", "monitored_regions", ["geom"], unique=False, postgresql_using="gist", postgresql_ops={}
    )
    op.create_index(op.f("ix_monitored_regions_territory_id"), "monitored_regions", ["territory_id"], unique=False)
    op.create_table(
        "password_reset_tokens",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_password_reset_tokens_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_password_reset_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_password_reset_tokens_token_hash")),
    )
    op.create_index(op.f("ix_password_reset_tokens_user_id"), "password_reset_tokens", ["user_id"], unique=False)
    op.create_table(
        "reports",
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("format", postgresql.ENUM(name="report_format", create_type=False), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("filters", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("file_name", sa.String(length=128), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("alert_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], name=op.f("fk_reports_created_by_id_users"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reports")),
    )
    op.create_index(op.f("ix_reports_created_at"), "reports", ["created_at"], unique=False)
    op.create_index(op.f("ix_reports_created_by_id"), "reports", ["created_by_id"], unique=False)
    op.create_table(
        "satellite_scenes",
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("scene_id", sa.String(length=128), nullable=False),
        sa.Column("collection", sa.String(length=64), nullable=False),
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cloud_cover", sa.Float(), nullable=True),
        sa.Column("epsg", sa.Integer(), nullable=False),
        sa.Column("tile_id", sa.String(length=16), nullable=True),
        sa.Column("assets", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_id"], ["satellite_sources.id"], name=op.f("fk_satellite_scenes_source_id_satellite_sources"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_satellite_scenes")),
        sa.UniqueConstraint("scene_id", name=op.f("uq_satellite_scenes_scene_id")),
    )
    op.create_index(op.f("ix_satellite_scenes_acquired_at"), "satellite_scenes", ["acquired_at"], unique=False)
    op.create_table(
        "user_preferences",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("notify_email", sa.String(length=254), nullable=True),
        sa.Column("notifications_enabled", sa.Boolean(), nullable=False),
        sa.Column("min_severity", postgresql.ENUM(name="severity", create_type=False), nullable=False),
        sa.Column("frequency", postgresql.ENUM(name="notification_frequency", create_type=False), nullable=False),
        sa.Column("region_ids", postgresql.ARRAY(sa.UUID()), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("signals", postgresql.ARRAY(sa.String(length=32)), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("last_digest_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_user_preferences_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_user_preferences")),
    )
    op.create_table(
        "processing_jobs",
        sa.Column("region_id", sa.Uuid(), nullable=False),
        sa.Column("status", postgresql.ENUM(name="job_status", create_type=False), nullable=False),
        sa.Column("reference_start", sa.Date(), nullable=False),
        sa.Column("reference_end", sa.Date(), nullable=False),
        sa.Column("observation_start", sa.Date(), nullable=False),
        sa.Column("observation_end", sa.Date(), nullable=False),
        sa.Column("progress", sa.Float(), nullable=False),
        sa.Column("stage", sa.String(length=32), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("task_id", sa.String(length=64), nullable=True),
        sa.Column("trigger", sa.String(length=16), nullable=False),
        sa.Column("requested_by_id", sa.Uuid(), nullable=True),
        sa.Column("model_version_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("progress >= 0 AND progress <= 1", name=op.f("ck_processing_jobs_progress_range")),
        sa.CheckConstraint("reference_end < observation_start", name=op.f("ck_processing_jobs_reference_before_observation")),
        sa.CheckConstraint(
            "reference_start <= reference_end AND observation_start <= observation_end", name=op.f("ck_processing_jobs_windows_ordered")
        ),
        sa.ForeignKeyConstraint(
            ["model_version_id"],
            ["model_versions.id"],
            name=op.f("fk_processing_jobs_model_version_id_model_versions"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["region_id"], ["monitored_regions.id"], name=op.f("fk_processing_jobs_region_id_monitored_regions"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_id"], ["users.id"], name=op.f("fk_processing_jobs_requested_by_id_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_processing_jobs")),
    )
    op.create_index(op.f("ix_processing_jobs_created_at"), "processing_jobs", ["created_at"], unique=False)
    op.create_index(op.f("ix_processing_jobs_region_id"), "processing_jobs", ["region_id"], unique=False)
    op.create_index(op.f("ix_processing_jobs_status"), "processing_jobs", ["status"], unique=False)
    op.create_index(
        "uq_active_job_per_window",
        "processing_jobs",
        ["region_id", "reference_start", "reference_end", "observation_start", "observation_end"],
        unique=True,
        postgresql_where="status IN ('queued', 'running')",
    )
    op.create_geospatial_table(
        "detection_results",
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("region_id", sa.Uuid(), nullable=False),
        sa.Column("model_version_id", sa.Uuid(), nullable=False),
        sa.Column("contract_version", sa.String(length=8), nullable=False),
        sa.Column("quality_ok", sa.Boolean(), nullable=False),
        sa.Column("quality_notes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("analysed_area_ha", sa.Float(), nullable=False),
        sa.Column("changed_area_ha", sa.Float(), nullable=False),
        sa.Column("reference_valid_fraction", sa.Float(), nullable=False),
        sa.Column("observation_valid_fraction", sa.Float(), nullable=False),
        sa.Column("reference_first", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reference_last", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observation_first", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observation_last", sa.DateTime(timezone=True), nullable=False),
        sa.Column("artifacts", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "extent",
            Geometry(geometry_type="POLYGON", srid=4326, dimension=2, spatial_index=False, from_text="ST_GeomFromEWKT", name="geometry"),
            nullable=True,
        ),
        sa.Column("parameters", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"], ["processing_jobs.id"], name=op.f("fk_detection_results_job_id_processing_jobs"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["model_version_id"],
            ["model_versions.id"],
            name=op.f("fk_detection_results_model_version_id_model_versions"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["region_id"], ["monitored_regions.id"], name=op.f("fk_detection_results_region_id_monitored_regions"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_detection_results")),
        sa.UniqueConstraint("job_id", name=op.f("uq_detection_results_job_id")),
    )
    op.create_geospatial_index(
        "idx_detection_results_extent", "detection_results", ["extent"], unique=False, postgresql_using="gist", postgresql_ops={}
    )
    op.create_index(op.f("ix_detection_results_created_at"), "detection_results", ["created_at"], unique=False)
    op.create_index(op.f("ix_detection_results_region_id"), "detection_results", ["region_id"], unique=False)
    op.create_table(
        "job_scenes",
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("scene_id", sa.Uuid(), nullable=False),
        sa.Column("period", sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["processing_jobs.id"], name=op.f("fk_job_scenes_job_id_processing_jobs"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["scene_id"], ["satellite_scenes.id"], name=op.f("fk_job_scenes_scene_id_satellite_scenes"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("job_id", "scene_id", name=op.f("pk_job_scenes")),
    )
    op.create_geospatial_table(
        "alerts",
        sa.Column("number", sa.Integer(), server_default=sa.text("nextval('alert_number_seq')"), nullable=False),
        sa.Column("region_id", sa.Uuid(), nullable=False),
        sa.Column("territory_id", sa.Uuid(), nullable=False),
        sa.Column(
            "geom",
            Geometry(
                geometry_type="MULTIPOLYGON",
                srid=4326,
                dimension=2,
                spatial_index=False,
                from_text="ST_GeomFromEWKT",
                name="geometry",
                nullable=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "centroid",
            Geometry(
                geometry_type="POINT",
                srid=4326,
                dimension=2,
                spatial_index=False,
                from_text="ST_GeomFromEWKT",
                name="geometry",
                nullable=False,
            ),
            nullable=False,
        ),
        sa.Column("area_ha", sa.Float(), nullable=False),
        sa.Column("severity", postgresql.ENUM(name="severity", create_type=False), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("signal", postgresql.ENUM(name="change_signal", create_type=False), nullable=False),
        sa.Column("status", postgresql.ENUM(name="alert_status", create_type=False), nullable=False),
        sa.Column("reference_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observation_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("first_detected_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_detected_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("detection_count", sa.Integer(), nullable=False),
        sa.Column("image_quality", sa.Float(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("model_version_id", sa.Uuid(), nullable=False),
        sa.Column("latest_result_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("area_ha > 0", name=op.f("ck_alerts_area_positive")),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name=op.f("ck_alerts_confidence_range")),
        sa.ForeignKeyConstraint(
            ["latest_result_id"], ["detection_results.id"], name=op.f("fk_alerts_latest_result_id_detection_results"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["model_version_id"], ["model_versions.id"], name=op.f("fk_alerts_model_version_id_model_versions"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["region_id"], ["monitored_regions.id"], name=op.f("fk_alerts_region_id_monitored_regions"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["territory_id"], ["territories.id"], name=op.f("fk_alerts_territory_id_territories"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_alerts")),
        sa.UniqueConstraint("number", name=op.f("uq_alerts_number")),
    )
    op.create_geospatial_index("idx_alerts_centroid", "alerts", ["centroid"], unique=False, postgresql_using="gist", postgresql_ops={})
    op.create_geospatial_index("idx_alerts_geom", "alerts", ["geom"], unique=False, postgresql_using="gist", postgresql_ops={})
    op.create_index(op.f("ix_alerts_last_detected_at"), "alerts", ["last_detected_at"], unique=False)
    op.create_index(op.f("ix_alerts_region_id"), "alerts", ["region_id"], unique=False)
    op.create_index(op.f("ix_alerts_severity"), "alerts", ["severity"], unique=False)
    op.create_index(op.f("ix_alerts_status"), "alerts", ["status"], unique=False)
    op.create_index("ix_alerts_status_severity", "alerts", ["status", "severity"], unique=False)
    op.create_index(op.f("ix_alerts_territory_id"), "alerts", ["territory_id"], unique=False)
    op.create_table(
        "alert_events",
        sa.Column("alert_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("type", postgresql.ENUM(name="alert_event_type", create_type=False), nullable=False),
        sa.Column("from_status", postgresql.ENUM(name="alert_status", create_type=False), nullable=True),
        sa.Column("to_status", postgresql.ENUM(name="alert_status", create_type=False), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("result_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("char_length(comment) <= 4000", name=op.f("ck_alert_events_comment_length")),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], name=op.f("fk_alert_events_actor_id_users"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["alert_id"], ["alerts.id"], name=op.f("fk_alert_events_alert_id_alerts"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["result_id"], ["detection_results.id"], name=op.f("fk_alert_events_result_id_detection_results"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_alert_events")),
    )
    op.create_index(op.f("ix_alert_events_alert_id"), "alert_events", ["alert_id"], unique=False)
    op.create_geospatial_table(
        "detected_polygons",
        sa.Column("result_id", sa.Uuid(), nullable=False),
        sa.Column("alert_id", sa.Uuid(), nullable=True),
        sa.Column(
            "geom",
            Geometry(
                geometry_type="MULTIPOLYGON",
                srid=4326,
                dimension=2,
                spatial_index=False,
                from_text="ST_GeomFromEWKT",
                name="geometry",
                nullable=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "centroid",
            Geometry(
                geometry_type="POINT",
                srid=4326,
                dimension=2,
                spatial_index=False,
                from_text="ST_GeomFromEWKT",
                name="geometry",
                nullable=False,
            ),
            nullable=False,
        ),
        sa.Column("area_ha", sa.Float(), nullable=False),
        sa.Column("mean_score", sa.Float(), nullable=False),
        sa.Column("max_score", sa.Float(), nullable=False),
        sa.Column("severity", postgresql.ENUM(name="severity", create_type=False), nullable=False),
        sa.Column("signal", postgresql.ENUM(name="change_signal", create_type=False), nullable=False),
        sa.Column("mean_ndvi_drop", sa.Float(), nullable=False),
        sa.Column("mean_nbr_drop", sa.Float(), nullable=False),
        sa.Column("valid_fraction", sa.Float(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("area_ha > 0", name=op.f("ck_detected_polygons_area_positive")),
        sa.CheckConstraint("mean_score BETWEEN 0 AND 1 AND max_score BETWEEN 0 AND 1", name=op.f("ck_detected_polygons_score_range")),
        sa.ForeignKeyConstraint(["alert_id"], ["alerts.id"], name=op.f("fk_detected_polygons_alert_id_alerts"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["result_id"], ["detection_results.id"], name=op.f("fk_detected_polygons_result_id_detection_results"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_detected_polygons")),
    )
    op.create_geospatial_index(
        "idx_detected_polygons_centroid", "detected_polygons", ["centroid"], unique=False, postgresql_using="gist", postgresql_ops={}
    )
    op.create_geospatial_index(
        "idx_detected_polygons_geom", "detected_polygons", ["geom"], unique=False, postgresql_using="gist", postgresql_ops={}
    )
    op.create_index(op.f("ix_detected_polygons_alert_id"), "detected_polygons", ["alert_id"], unique=False)
    op.create_index(op.f("ix_detected_polygons_result_id"), "detected_polygons", ["result_id"], unique=False)
    op.create_table(
        "notifications",
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("alert_id", sa.Uuid(), nullable=True),
        sa.Column("report_id", sa.Uuid(), nullable=True),
        sa.Column("kind", postgresql.ENUM(name="notification_kind", create_type=False), nullable=False),
        sa.Column("status", postgresql.ENUM(name="notification_status", create_type=False), nullable=False),
        sa.Column("to_email", sa.String(length=254), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["alert_id"], ["alerts.id"], name=op.f("fk_notifications_alert_id_alerts"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], name=op.f("fk_notifications_report_id_reports"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_notifications_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notifications")),
    )
    op.create_index(op.f("ix_notifications_created_at"), "notifications", ["created_at"], unique=False)
    op.create_index(op.f("ix_notifications_user_id"), "notifications", ["user_id"], unique=False)
    op.create_index("uq_notification_user_alert", "notifications", ["user_id", "alert_id"], unique=True, postgresql_where="kind = 'alert'")
    # ### fin de los comandos de Alembic ###


def downgrade() -> None:
    # ### comandos autogenerados por Alembic - ¡revísenlos! ###
    op.drop_index("uq_notification_user_alert", table_name="notifications", postgresql_where="kind = 'alert'")
    op.drop_index(op.f("ix_notifications_user_id"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_created_at"), table_name="notifications")
    op.drop_table("notifications")
    op.drop_index(op.f("ix_detected_polygons_result_id"), table_name="detected_polygons")
    op.drop_index(op.f("ix_detected_polygons_alert_id"), table_name="detected_polygons")
    op.drop_geospatial_index("idx_detected_polygons_geom", table_name="detected_polygons", postgresql_using="gist", column_name="geom")
    op.drop_geospatial_index(
        "idx_detected_polygons_centroid", table_name="detected_polygons", postgresql_using="gist", column_name="centroid"
    )
    op.drop_geospatial_table("detected_polygons")
    op.drop_index(op.f("ix_alert_events_alert_id"), table_name="alert_events")
    op.drop_table("alert_events")
    op.drop_index(op.f("ix_alerts_territory_id"), table_name="alerts")
    op.drop_index("ix_alerts_status_severity", table_name="alerts")
    op.drop_index(op.f("ix_alerts_status"), table_name="alerts")
    op.drop_index(op.f("ix_alerts_severity"), table_name="alerts")
    op.drop_index(op.f("ix_alerts_region_id"), table_name="alerts")
    op.drop_index(op.f("ix_alerts_last_detected_at"), table_name="alerts")
    op.drop_geospatial_index("idx_alerts_geom", table_name="alerts", postgresql_using="gist", column_name="geom")
    op.drop_geospatial_index("idx_alerts_centroid", table_name="alerts", postgresql_using="gist", column_name="centroid")
    op.drop_geospatial_table("alerts")
    op.drop_table("job_scenes")
    op.drop_index(op.f("ix_detection_results_region_id"), table_name="detection_results")
    op.drop_index(op.f("ix_detection_results_created_at"), table_name="detection_results")
    op.drop_geospatial_index("idx_detection_results_extent", table_name="detection_results", postgresql_using="gist", column_name="extent")
    op.drop_geospatial_table("detection_results")
    op.drop_index("uq_active_job_per_window", table_name="processing_jobs", postgresql_where="status IN ('queued', 'running')")
    op.drop_index(op.f("ix_processing_jobs_status"), table_name="processing_jobs")
    op.drop_index(op.f("ix_processing_jobs_region_id"), table_name="processing_jobs")
    op.drop_index(op.f("ix_processing_jobs_created_at"), table_name="processing_jobs")
    op.drop_table("processing_jobs")
    op.drop_table("user_preferences")
    op.drop_index(op.f("ix_satellite_scenes_acquired_at"), table_name="satellite_scenes")
    op.drop_table("satellite_scenes")
    op.drop_index(op.f("ix_reports_created_by_id"), table_name="reports")
    op.drop_index(op.f("ix_reports_created_at"), table_name="reports")
    op.drop_table("reports")
    op.drop_index(op.f("ix_password_reset_tokens_user_id"), table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
    op.drop_index(op.f("ix_monitored_regions_territory_id"), table_name="monitored_regions")
    op.drop_geospatial_index("idx_monitored_regions_geom", table_name="monitored_regions", postgresql_using="gist", column_name="geom")
    op.drop_geospatial_table("monitored_regions")
    op.drop_index(op.f("ix_cookie_consents_subject_id"), table_name="cookie_consents")
    op.drop_table("cookie_consents")
    op.drop_index(op.f("ix_auth_sessions_user_id"), table_name="auth_sessions")
    op.drop_index(op.f("ix_auth_sessions_previous_token_hash"), table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_index(op.f("ix_audit_logs_created_at"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_actor_id"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_action"), table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("uq_users_email_lower", table_name="users")
    op.drop_table("users")
    op.drop_geospatial_index("idx_territories_geom", table_name="territories", postgresql_using="gist", column_name="geom")
    op.drop_geospatial_table("territories")
    op.drop_table("satellite_sources")
    op.drop_table("model_versions")
    # ### fin de los comandos de Alembic ###
    postgresql.ENUM(name="user_role").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="report_format").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="severity").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="notification_frequency").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="job_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="change_signal").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="alert_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="alert_event_type").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="notification_kind").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="notification_status").drop(op.get_bind(), checkfirst=True)
    op.execute("DROP SEQUENCE IF EXISTS alert_number_seq")
