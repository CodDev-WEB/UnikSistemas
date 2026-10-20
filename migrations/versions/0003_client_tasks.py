"""Add client-linked document and follow-up tasks.

Revision ID: 0003_client_tasks
Revises: 0002_client_import_batches
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_client_tasks"
down_revision = "0002_client_import_batches"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "client_tasks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("client_id", sa.String(length=36), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("assigned_to_user_id", sa.String(length=36), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=True),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("priority", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assigned_to_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_client_tasks_tenant_status_due",
        "client_tasks",
        ["tenant_id", "status", "due_date"],
    )
    op.create_index(
        "ix_client_tasks_tenant_client_created",
        "client_tasks",
        ["tenant_id", "client_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_client_tasks_tenant_client_created", table_name="client_tasks")
    op.drop_index("ix_client_tasks_tenant_status_due", table_name="client_tasks")
    op.drop_table("client_tasks")
