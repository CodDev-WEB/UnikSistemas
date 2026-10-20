"""Add in-app notification inbox and email outbox.

Revision ID: 0005_notifications
Revises: 0004_document_intake
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_notifications"
down_revision = "0004_document_intake"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("recipient_user_id", sa.String(length=36), nullable=False),
        sa.Column("event_key", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("message", sa.String(length=1500), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.String(length=36), nullable=False),
        sa.Column("action_url", sa.String(length=255), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("email_status", sa.String(length=20), nullable=False),
        sa.Column("email_attempts", sa.Integer(), nullable=False),
        sa.Column("email_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("email_last_error", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recipient_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "recipient_user_id", "event_key",
            name="uq_notifications_tenant_recipient_event",
        ),
    )
    op.create_index(
        "ix_notifications_tenant_recipient_created",
        "notifications",
        ["tenant_id", "recipient_user_id", "created_at"],
    )
    op.create_index(
        "ix_notifications_email_queue",
        "notifications",
        ["email_status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_notifications_email_queue", table_name="notifications")
    op.drop_index("ix_notifications_tenant_recipient_created", table_name="notifications")
    op.drop_table("notifications")
