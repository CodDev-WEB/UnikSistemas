"""Track the last explicit email queue time for stale-backlog policy.

Revision ID: 0008_notification_queue_age
Revises: 0007_antivirus_operations
"""
from alembic import op
import sqlalchemy as sa

revision = "0008_notification_queue_age"
down_revision = "0007_antivirus_operations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "notifications",
        sa.Column("email_queued_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Existing pending notifications retain their original age. Turning SMTP on
    # must not make weeks-old records look like newly queued messages.
    op.execute(
        "UPDATE notifications SET email_queued_at = created_at WHERE email_queued_at IS NULL"
    )
    op.alter_column(
        "notifications",
        "email_queued_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )


def downgrade() -> None:
    op.drop_column("notifications", "email_queued_at")
