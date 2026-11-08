"""Tenant models (DB_MODEL.md 4.2).

Tenants and OIDC configurations are shared parents: they are never deleted,
so FKs to them are ON DELETE RESTRICT. Queries on tenant data tables always
filter by tenant_id (tenant isolation, DB_MODEL.md 6). None of these tables
has DB CHECK constraints (DB_MODEL.md 1); the application validates values.
"""

import uuid
from collections.abc import Mapping
from datetime import datetime
from enum import IntEnum
from typing import Any

from sqlalchemy import ARRAY, ForeignKey, Index, String, Text, false, func, text
from sqlalchemy.orm import Mapped, mapped_column

from passport.db.base import Base, IntEnumType


class TenantStatus(IntEnum):
    """Tenant status stored in tenants.tenant_status.

    A platform admin moves a tenant between any of these states
    (DB_MODEL.md 5.3). Tenant-scoped access requires ACTIVE.
    """

    ACTIVE = 1
    SUSPENDED = 2
    DEACTIVATED = 3


class OidcProviderType(IntEnum):
    """External OIDC provider product.

    Support for logout and revocation detection is verified against the
    actual provider before enabling, never assumed from the product name
    (FR-OIDC-017-01).
    """

    KEYCLOAK = 1
    AUTH0 = 2


class OidcConfigurationStatus(IntEnum):
    """Whether a tenant's OIDC login is usable.

    ENABLED <-> DISABLED. Disabling replaces deletion, and ENABLED -> DISABLED
    is a trust change (see TenantOidcConfiguration).
    """

    ENABLED = 1
    DISABLED = 2


class OidcValidationStatus(IntEnum):
    """Result of the last check of a configuration against its provider."""

    OK = 1
    FAILED = 2


class OidcValidationError(IntEnum):
    """Why the last provider check failed."""

    DISCOVERY_UNREACHABLE = 1  # Discovery document could not be fetched.
    ISSUER_MISMATCH = 2  # Discovered issuer differs from the configured one.
    JWKS_UNREACHABLE = 3  # Provider signing keys could not be fetched.
    INVALID_CLIENT = 4  # Provider rejected client_id or client_secret.
    # Provider cannot map logout/revocation to exact sessions or tokens.
    UNSUPPORTED_LIFECYCLE_BINDING = 5


class TenantRole(IntEnum):
    """Role of a member inside one tenant."""

    # Manages the tenant. The tenant creator starts as ADMIN. The last active
    # ADMIN cannot be demoted, removed or withdraw (409 last_tenant_admin);
    # active ADMIN rows are locked FOR UPDATE before counting.
    ADMIN = 1
    # Regular member; the default and the role given by OIDC auto-join.
    MEMBER = 2


class MembershipStatus(IntEnum):
    """Membership status stored in tenant_memberships.membership_status.

    Key 1 is retired and must not be reused. Transitions (DB_MODEL.md 5.2):
    - none -> ACTIVE: OIDC login auto-join, tenant admin adding an existing
      user, or tenant creation (creator as ADMIN).
    - ACTIVE <-> SUSPENDED by a tenant admin.
    - ACTIVE or SUSPENDED -> REMOVED by a tenant admin. REMOVED is final for
      that row; rejoining creates a new row.
    - Any status -> row deleted when the user withdraws.
    Token issue and refresh never create or activate a membership.
    """

    ACTIVE = 2
    SUSPENDED = 3
    REMOVED = 4


class MembershipRemovalReason(IntEnum):
    """Why a membership became REMOVED. Keys 2 and 3 are retired."""

    ADMIN_REMOVED = 1


class Tenant(Base):
    """Global tenant shared by every integrated SaaS application.

    The anchor for memberships and service subscriptions; tenant_status gates
    tenant-scoped access. Creating a tenant inserts the creator's ADMIN
    membership in the same transaction, and a duplicate tenant_code fails
    with 409 already_exists.
    """

    __tablename__ = "tenants"
    __mapper_args__: Mapping[str, Any] = {"eager_defaults": True}

    tenant_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    # Unique business key; never changes after creation.
    tenant_code: Mapped[str] = mapped_column(String(32), unique=True)
    is_system: Mapped[bool] = mapped_column(server_default=false())
    tenant_name: Mapped[str] = mapped_column(String(100))
    # Changed only by a platform admin (adminUpdateTenantStatus).
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
    # Optional link to a record in another system: its ID and where it lives.
    external_id: Mapped[str | None] = mapped_column(String(50))
    external_source: Mapped[str | None] = mapped_column(String(50))


class TenantOidcConfiguration(Base):
    """A tenant's external OIDC provider and client settings.

    One row per tenant; it is disabled instead of deleted (FR-OIDC-010, D-06).

    - Trust change = issuer, client_id or client_secret change, or ENABLED ->
      DISABLED. In the same transaction as the update, end every open login
      of this config_id with OIDC_TRUST_CHANGED and delete its pending OIDC
      login transactions and unused identity link tickets. A display_name
      change keeps user sessions and pending flows.
    - Lock order is the tenant row, then this row: FOR SHARE for login start,
      callback and link ticket use; FOR UPDATE for configuration changes.
      Calls to the provider run outside these locks.
    - Before enabling, test the provider's logout and revocation detection
      for exact session/token mapping, and reject what cannot be mapped with
      UNSUPPORTED_LIFECYCLE_BINDING (FR-OIDC-017-01).
    """

    __tablename__ = "tenant_oidc_configurations"
    __mapper_args__: Mapping[str, Any] = {"eager_defaults": True}

    config_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    # UNIQUE: at most one configuration per tenant.
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.tenant_id", ondelete="RESTRICT"), unique=True
    )
    provider_type: Mapped[OidcProviderType] = mapped_column(
        IntEnumType(OidcProviderType)
    )
    # Label shown on login options; changing it is not a trust change.
    display_name: Mapped[str] = mapped_column(String(100))
    # Must start with https:// (checked by the application).
    issuer: Mapped[str] = mapped_column(String(2048))
    client_id: Mapped[str] = mapped_column(String(255))
    # Proposed: AES-256-GCM ciphertext prefixed with the key ID, so keys can
    # rotate. The API only reports whether a secret is set.
    client_secret_ciphertext: Mapped[bytes]
    # Scopes requested in the authorization request.
    scopes: Mapped[list[str]] = mapped_column(
        ARRAY(Text), server_default=text("'{openid,email,profile}'")
    )
    config_status: Mapped[OidcConfigurationStatus] = mapped_column(
        IntEnumType(OidcConfigurationStatus)
    )
    # Outcome and time of the last provider check.
    last_validation_status: Mapped[OidcValidationStatus] = mapped_column(
        IntEnumType(OidcValidationStatus)
    )
    last_validation_checked_at: Mapped[datetime]
    # Failure reason of the last check; NULL when it passed.
    last_validation_error_code: Mapped[OidcValidationError | None] = mapped_column(
        IntEnumType(OidcValidationError)
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )


class TenantMembership(Base):
    """A user's membership in a tenant: role and status.

    The basis for tenant access and tenant admin rights. Only existing user
    accounts can be members.

    - OIDC login (intent = login) to a tenant the user has no membership
      history in auto-creates an ACTIVE MEMBER row with joined_at, in the
      same transaction as the user, identity and login. Identity linking and
      reauthentication never grant membership.
    - A tenant admin can add an existing user: ACTIVE with joined_at set;
      404 for an unknown user, 409 for a current membership. Removal history
      cannot be bypassed this way (rejoin approval is P1).
    - REMOVED and SUSPENDED rows are never restored automatically. REMOVED
      rows stay for audit and the P1 rejoin decision while the account exists
      (FR-MEM-008); withdrawal cascades every row, REMOVED ones included.
    """

    __tablename__ = "tenant_memberships"
    __table_args__ = (
        # One current (non-REMOVED) membership per tenant and user (FR-MEM-005).
        Index(
            "uq_tenant_memberships_tenant_user",
            "tenant_id",
            "user_id",
            unique=True,
            postgresql_where=text(
                f"membership_status <> {MembershipStatus.REMOVED.value}"
            ),
        ),
        # Tenant member listing by status. Named explicitly because the naming
        # convention would only use the first column.
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
    # Indexed for listMyTenants; deleted with the user.
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
    # When the membership first became ACTIVE.
    joined_at: Mapped[datetime | None]
    # Set when the membership becomes REMOVED.
    removed_at: Mapped[datetime | None]
    removed_reason: Mapped[MembershipRemovalReason | None] = mapped_column(
        IntEnumType(MembershipRemovalReason)
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )
