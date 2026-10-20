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
