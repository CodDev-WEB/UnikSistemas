"""Add public document upload links and client attachments.

Revision ID: 0004_document_intake
Revises: 0003_client_tasks
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_document_intake"
down_revision = "0003_client_tasks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_upload_links",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("max_uploads", sa.Integer(), nullable=False),
        sa.Column("upload_count", sa.Integer(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["client_tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_document_upload_links_token_hash"),
    )
    op.create_index(
        "ix_document_upload_links_tenant_task",
        "document_upload_links",
        ["tenant_id", "task_id"],
    )
    op.create_table(
        "client_documents",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("upload_link_id", sa.String(length=36), nullable=True),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("review_status", sa.String(length=20), nullable=False),
        sa.Column("review_note", sa.String(length=1000), nullable=True),
        sa.Column("reviewed_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["client_tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["upload_link_id"], ["document_upload_links.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index(
        "ix_client_documents_tenant_task_created",
        "client_documents",
        ["tenant_id", "task_id", "created_at"],
    )
    op.create_index(
        "ix_client_documents_tenant_status",
        "client_documents",
        ["tenant_id", "review_status"],
    )


def downgrade() -> None:
    op.drop_index("ix_client_documents_tenant_status", table_name="client_documents")
    op.drop_index("ix_client_documents_tenant_task_created", table_name="client_documents")
    op.drop_table("client_documents")
    op.drop_index("ix_document_upload_links_tenant_task", table_name="document_upload_links")
    op.drop_table("document_upload_links")
