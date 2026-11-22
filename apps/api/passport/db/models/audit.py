"""Audit log model (DB_MODEL.md 4.6).

Audit records outlive what they describe: there are no FKs, and user
withdrawal keeps them. The application account may INSERT and DELETE (for the
retention job) but not UPDATE; revision 0001 revokes that privilege.
"""

import uuid
from datetime import datetime
from enum import IntEnum
from ipaddress import IPv4Address, IPv6Address
from typing import Any

from sqlalchemy import Index, String, func, text
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from passport.db.base import Base, IntEnumType


class AuditAction(IntEnum):
    """Audited event: the contract's x-audit-event name.

    Member names replace the dot of the external name with "_", which is not
    reversible (TENANT_APPLICATION_CHANGED is tenant_application.changed), so
    API adapters map names explicitly. Retired keys 9, 10, 12, 15-21, 24, 26,
    29-31 and 44 must not be reused.
    """

    USER_SIGNUP_REQUESTED = 1
    USER_EMAIL_VERIFIED = 2
    AUTH_LOGIN_SUCCEEDED = 3
    AUTH_LOGIN_FAILED = 4
    AUTH_LOGOUT = 5
    AUTH_LOGOUT_ALL = 6
    AUTH_REAUTHENTICATED = 7
    USER_PROFILE_UPDATED = 8
    USER_PASSWORD_CHANGED = 11
    USER_WITHDRAWN = 13
    IDENTITY_LINKED = 14
    TENANT_CREATED = 22
    TENANT_UPDATED = 23
    TENANT_OIDC_CONFIGURATION_CHANGED = 25
    MEMBERSHIP_UPDATED = 27
    MEMBERSHIP_REMOVED = 28
    TENANT_APPLICATION_CHANGED = 32
    ADMIN_TENANTS_LISTED = 33
    TENANT_STATUS_CHANGED = 34
    ADMIN_USERS_SEARCHED = 35
    ADMIN_USER_VIEWED = 36
    USER_STATUS_CHANGED = 37
    APPLICATION_CREATED = 38
    APPLICATION_UPDATED = 39
    APPLICATION_SECRET_ROTATED = 40
    AUTH_OIDC_LOGIN_SUCCEEDED = 41
    AUTH_OIDC_LOGIN_FAILED = 42
    USER_CREATED_FROM_OIDC = 43
    MEMBERSHIP_CREATED = 45


class AuditResult(IntEnum):
    """Outcome of the audited action."""

    SUCCESS = 1
    FAILURE = 2


class AuditActorType(IntEnum):
    """Who performed the audited action."""

    USER = 1  # actor_id is a user_id.
    PLATFORM_ADMIN = 2  # actor_id is the admin's user_id.
    APPLICATION = 3  # actor_id is an application_id (service API call).
    SYSTEM = 4  # Passport itself; no actor_id.


class AuditTargetType(IntEnum):
    """Kind of resource the audited action touched. Keys 9-11 and 13 are retired."""

    USER = 1
    TENANT = 2
    TENANT_MEMBERSHIP = 3
    APPLICATION = 4
    TENANT_APPLICATION = 5
    TENANT_OIDC_CONFIGURATION = 6
    LOGIN = 7  # A user session (user_sessions).
    IDENTITY = 8  # A linked external identity (user_identities).
    USER_PROFILE = 12


class AuditLog(Base):
    """Append-only audit trail of security-relevant actions (NFR-SEC-007).

    Records who did what to which resource, when, with what result and why,
    for operations checks and incident investigation. Every operation with an
    x-audit-event in the contract writes one row.

    - Never store secrets, their hashes, tokens or sensitive personal data
      (NFR-SEC-008). Withdrawal records only the former user_id, the time and
      the deletion result.
    - Rows are purged 365 days after occurred_at (NFR-SEC-007-01).
    """

    __tablename__ = "audit_logs"
    __table_args__ = (
        # Audit search within a tenant; named explicitly because the naming
        # convention would only use the first column.
        Index("ix_audit_logs_tenant_id_occurred_at", "tenant_id", "occurred_at"),
    )

    log_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    # Indexed for the retention job.
    occurred_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
    action: Mapped[AuditAction] = mapped_column(IntEnumType(AuditAction))
    result: Mapped[AuditResult] = mapped_column(IntEnumType(AuditResult))
    actor_type: Mapped[AuditActorType] = mapped_column(IntEnumType(AuditActorType))
    # user_id or application_id, depending on actor_type. No FK: the actor may
    # be deleted later.
    actor_id: Mapped[uuid.UUID | None]
    # Tenant the action applies to, if any.
    tenant_id: Mapped[uuid.UUID | None]
    target_type: Mapped[AuditTargetType | None] = mapped_column(
        IntEnumType(AuditTargetType)
    )
    # ID of the target resource, as text.
    target_id: Mapped[str | None] = mapped_column(String(64))
    # X-Request-ID of the HTTP request.
    request_id: Mapped[str | None] = mapped_column(String(128))
    # Proposed: client IP address.
    source_ip: Mapped[IPv4Address | IPv6Address | None] = mapped_column(INET)
    # Reason an admin gave for the action or lookup.
    reason: Mapped[str | None] = mapped_column(String(500))
    # Extra context as a versioned JSON record; nested states and types use
    # their string names (DB_MODEL.md 1.1).
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'"))
