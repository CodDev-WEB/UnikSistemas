"""Track ClamAV operational health and infected quarantine retention.

Revision ID: 0007_antivirus_operations
Revises: 0006_document_antivirus
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_antivirus_operations"
down_revision = "0006_document_antivirus"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "client_documents",
        sa.Column("quarantine_purged_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "antivirus_health",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="unknown", nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("signature_database_version", sa.String(length=80), nullable=True),
        sa.Column("signature_database_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("incident_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_cleanup_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("antivirus_health")
    op.drop_column("client_documents", "quarantine_purged_at")
