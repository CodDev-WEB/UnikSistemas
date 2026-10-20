"""Add quarantine scanning state to client documents.

Revision ID: 0006_document_antivirus
Revises: 0005_notifications
"""
from alembic import op
import sqlalchemy as sa

revision = "0006_document_antivirus"
down_revision = "0005_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "client_documents",
        sa.Column("scan_status", sa.String(length=20), server_default="pending", nullable=False),
    )
    op.add_column(
        "client_documents",
        sa.Column("scan_attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.add_column(
        "client_documents",
        sa.Column("scan_last_attempt_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "client_documents",
        sa.Column("scan_completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "client_documents",
        sa.Column("scan_error", sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("client_documents", "scan_error")
    op.drop_column("client_documents", "scan_completed_at")
    op.drop_column("client_documents", "scan_last_attempt_at")
    op.drop_column("client_documents", "scan_attempts")
    op.drop_column("client_documents", "scan_status")
