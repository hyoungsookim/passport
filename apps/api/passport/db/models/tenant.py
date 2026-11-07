"""Tenant models (DB_MODEL.md 4.2)."""

import uuid
from collections.abc import Mapping
from datetime import datetime
from enum import IntEnum
from typing import Any

from sqlalchemy import ARRAY, ForeignKey, Index, String, Text, false, func, text
from sqlalchemy.orm import Mapped, mapped_column

from passport.db.base import Base, IntEnumType


class TenantStatus(IntEnum):
    ACTIVE = 1
    SUSPENDED = 2
    DEACTIVATED = 3


class OidcProviderType(IntEnum):
    KEYCLOAK = 1
    AUTH0 = 2


class OidcConfigurationStatus(IntEnum):
    ENABLED = 1
    DISABLED = 2


class OidcValidationStatus(IntEnum):
    OK = 1
    FAILED = 2


class OidcValidationError(IntEnum):
    DISCOVERY_UNREACHABLE = 1
    ISSUER_MISMATCH = 2
    JWKS_UNREACHABLE = 3
    INVALID_CLIENT = 4
    UNSUPPORTED_LIFECYCLE_BINDING = 5


class TenantRole(IntEnum):
    ADMIN = 1
    MEMBER = 2


class MembershipStatus(IntEnum):
    ACTIVE = 2
    SUSPENDED = 3
    REMOVED = 4


class MembershipRemovalReason(IntEnum):
    ADMIN_REMOVED = 1


class Tenant(Base):
    __tablename__ = "tenants"
    __mapper_args__: Mapping[str, Any] = {"eager_defaults": True}

    tenant_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    tenant_code: Mapped[str] = mapped_column(String(32), unique=True)
    is_system: Mapped[bool] = mapped_column(server_default=false())
    tenant_name: Mapped[str] = mapped_column(String(100))
    tenant_status: Mapped[TenantStatus] = mapped_column(
        IntEnumType(TenantStatus), server_default=text(str(TenantStatus.ACTIVE.value))
    )
    tenant_description: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )
    # No FK: withdrawal deletes the user row, and tenants must outlive it.
    created_by: Mapped[uuid.UUID]
    updated_by: Mapped[uuid.UUID]
    external_id: Mapped[str | None] = mapped_column(String(50))
    external_source: Mapped[str | None] = mapped_column(String(50))


class TenantOidcConfiguration(Base):
    __tablename__ = "tenant_oidc_configurations"
    __mapper_args__: Mapping[str, Any] = {"eager_defaults": True}

    config_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.tenant_id", ondelete="RESTRICT"), unique=True
    )
    provider_type: Mapped[OidcProviderType] = mapped_column(
        IntEnumType(OidcProviderType)
    )
    display_name: Mapped[str] = mapped_column(String(100))
    issuer: Mapped[str] = mapped_column(String(2048))
    client_id: Mapped[str] = mapped_column(String(255))
    client_secret_ciphertext: Mapped[bytes]
    scopes: Mapped[list[str]] = mapped_column(
        ARRAY(Text), server_default=text("'{openid,email,profile}'")
    )
    config_status: Mapped[OidcConfigurationStatus] = mapped_column(
        IntEnumType(OidcConfigurationStatus)
    )
    last_validation_status: Mapped[OidcValidationStatus] = mapped_column(
        IntEnumType(OidcValidationStatus)
    )
    last_validation_checked_at: Mapped[datetime]
    last_validation_error_code: Mapped[OidcValidationError | None] = mapped_column(
        IntEnumType(OidcValidationError)
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )


class TenantMembership(Base):
    __tablename__ = "tenant_memberships"
    __table_args__ = (
        Index(
            "uq_tenant_memberships_tenant_user",
            "tenant_id",
            "user_id",
            unique=True,
            postgresql_where=text(
                f"membership_status <> {MembershipStatus.REMOVED.value}"
            ),
        ),
        Index(
            "ix_tenant_memberships_tenant_id_membership_status",
            "tenant_id",
            "membership_status",
        ),
    )
    __mapper_args__: Mapping[str, Any] = {"eager_defaults": True}

    membership_id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid7
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.tenant_id", ondelete="RESTRICT")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), index=True
    )
    role_in_tenant: Mapped[TenantRole] = mapped_column(
        IntEnumType(TenantRole), server_default=text(str(TenantRole.MEMBER.value))
    )
    membership_status: Mapped[MembershipStatus] = mapped_column(
        IntEnumType(MembershipStatus),
        server_default=text(str(MembershipStatus.ACTIVE.value)),
    )
    joined_at: Mapped[datetime | None]
    removed_at: Mapped[datetime | None]
    removed_reason: Mapped[MembershipRemovalReason | None] = mapped_column(
        IntEnumType(MembershipRemovalReason)
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )
