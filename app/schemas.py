from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class TenantBootstrapRequest(BaseModel):
    tenant_name: str = Field(min_length=2, max_length=160)
    tenant_slug: str = Field(
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", min_length=2, max_length=80
    )
    owner_email: EmailStr
    owner_full_name: str = Field(min_length=2, max_length=160)
    owner_password: str = Field(min_length=12, max_length=128)

    @field_validator("tenant_name", "owner_full_name")
    @classmethod
    def strip_names(cls, value: str) -> str:
        return value.strip()

    @field_validator("owner_email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()


class LoginRequest(BaseModel):
    tenant_slug: str = Field(min_length=2, max_length=80)
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()


class TenantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    slug: str
    status: str


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    tenant_id: str
    email: EmailStr
    full_name: str
    role: str
    is_active: bool


class TenantBootstrapResponse(BaseModel):
    tenant: TenantRead
    owner: UserRead


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class MeResponse(BaseModel):
    user: UserRead
    tenant: TenantRead


class ClientCreate(BaseModel):
    legal_name: str = Field(min_length=2, max_length=200)
    trade_name: str | None = Field(default=None, max_length=200)
    tax_id: str | None = Field(default=None, max_length=32)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=32)
    status: Literal["active", "archived"] = "active"

    @field_validator("legal_name", "trade_name", "tax_id", "phone")
    @classmethod
    def strip_optional_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("email")
    @classmethod
    def normalize_optional_email(cls, value: EmailStr | None) -> str | None:
        return str(value).strip().lower() if value is not None else None


class ClientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    legal_name: str
    trade_name: str | None
    tax_id: str | None
    email: EmailStr | None
    phone: str | None
    status: str
    created_at: str | None = None

    @field_validator("created_at", mode="before")
    @classmethod
    def serialize_datetime(cls, value):
        return value.isoformat() if value is not None else None


class UserCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    role: Literal["admin", "accountant", "assistant", "viewer"] = "accountant"

    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("email")
    @classmethod
    def normalize_user_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=160)
    role: Literal["admin", "accountant", "assistant", "viewer"] | None = None
    is_active: bool | None = None

    @field_validator("full_name")
    @classmethod
    def normalize_updated_name(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None



class ClientImportRowRead(BaseModel):
    row_number: int
    legal_name: str | None = None
    trade_name: str | None = None
    tax_id: str | None = None
    email: str | None = None
    phone: str | None = None
    status: str | None = None
    errors: list[str] = Field(default_factory=list)


class ClientImportBatchRead(BaseModel):
    id: str
    filename: str
    status: Literal["ready", "invalid", "confirmed", "discarded"]
    total_rows: int
    imported_count: int
    rows: list[ClientImportRowRead]
    created_at: str | None = None
    confirmed_at: str | None = None



class ClientImportHistoryRead(BaseModel):
    id: str
    filename: str
    status: Literal["ready", "invalid", "confirmed", "discarded"]
    total_rows: int
    imported_count: int
    created_by_name: str | None = None
    created_at: str | None = None
    confirmed_at: str | None = None



class ClientTaskCreate(BaseModel):
    client_id: str = Field(min_length=1, max_length=36)
    title: str = Field(min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    kind: Literal["document", "follow_up", "routine"] = "document"
    priority: Literal["low", "normal", "high"] = "normal"
    due_date: date | None = None
    assigned_to_user_id: str | None = Field(default=None, max_length=36)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 2:
            raise ValueError("Informe uma descrição com pelo menos dois caracteres.")
        return cleaned

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class ClientTaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    kind: Literal["document", "follow_up", "routine"] | None = None
    priority: Literal["low", "normal", "high"] | None = None
    due_date: date | None = None
    assigned_to_user_id: str | None = Field(default=None, max_length=36)
    status: Literal["open", "received", "completed", "cancelled"] | None = None

    @field_validator("title")
    @classmethod
    def normalize_updated_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if len(cleaned) < 2:
            raise ValueError("Informe uma descrição com pelo menos dois caracteres.")
        return cleaned

    @field_validator("description")
    @classmethod
    def normalize_updated_description(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class ClientTaskRead(BaseModel):
    id: str
    client_id: str
    client_name: str
    title: str
    description: str | None = None
    kind: Literal["document", "follow_up", "routine"]
    priority: Literal["low", "normal", "high"]
    status: Literal["open", "received", "completed", "cancelled"]
    due_date: date | None = None
    assigned_to_user_id: str | None = None
    assigned_to_name: str | None = None
    created_by_user_id: str | None = None
    created_by_name: str | None = None
    completed_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class DocumentUploadLinkRead(BaseModel):
    id: str
    public_path: str
    expires_at: str
    max_uploads: int


class PublicDocumentUploadInfo(BaseModel):
    title: str
    description: str | None = None
    expires_at: str
    remaining_uploads: int
    max_file_size_bytes: int
    allowed_extensions: list[str]


class ClientDocumentRead(BaseModel):
    id: str
    task_id: str
    task_title: str
    client_name: str
    original_filename: str
    content_type: str
    file_size: int
    sha256: str
    review_status: Literal["pending", "accepted", "rejected"]
    review_note: str | None = None
    reviewed_by_name: str | None = None
    reviewed_at: str | None = None
    created_at: str | None = None


class ClientDocumentReviewUpdate(BaseModel):
    review_status: Literal["accepted", "rejected"]
    review_note: str | None = Field(default=None, max_length=1000)

    @field_validator("review_note")
    @classmethod
    def normalize_review_note(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class NotificationRead(BaseModel):
    id: str
    event_type: Literal["document_received", "task_assigned", "task_due"]
    title: str
    message: str
    entity_type: str
    entity_id: str
    action_url: str | None = None
    is_read: bool
    email_status: Literal["pending", "sent", "failed"]
    email_attempts: int
    email_sent_at: str | None = None
    created_at: str | None = None


class NotificationSummaryRead(BaseModel):
    created: int
    due_items_checked: int
    email_enabled: bool
    queued_email_count: int
    failed_email_count: int
