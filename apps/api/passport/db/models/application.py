"""Application models (DB_MODEL.md 4.3).

An application is a SaaS service registered with Passport. Applications are
shared parents and are never deleted, so FKs to them are ON DELETE RESTRICT.
Unlike users and tenants, applications carries DB CHECK constraints.
"""

import uuid
from collections.abc import Mapping
from datetime import datetime
from enum import IntEnum
from typing import Any

from sqlalchemy import ARRAY, CheckConstraint, ForeignKey, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from passport.db.base import Base, IntEnumType


class ApplicationStatus(IntEnum):
    """Status of an application, or of a tenant's use of it.

    Transitions (DB_MODEL.md 5.3):
    - applications.application_status: ACTIVE <-> INACTIVE.
    - tenant_applications.application_status: no row -> ACTIVE -> INACTIVE
      <-> ACTIVE.
    Both are read from the DB on every request, never from a cache.
    """

    ACTIVE = 1
    INACTIVE = 2


class Application(Base):
    """A registered SaaS application and its trusted service client.

    application_code is both the OAuth client_id and the Access Token "aud".
    The client secret authenticates server-to-server service API calls and
    the application's BFF client during SSO code exchange; one credential
    serves both (DB_MODEL.md 13, item 2).

    Secret rotation: the current hash moves to previous_client_secret_hash
    and stays valid until previous_secret_valid_until, so the service can
    switch without downtime. The previous-secret CHECK keeps those two
    columns NULL or set together.
    """

    __tablename__ = "applications"
    __table_args__ = (
        # Contract ApplicationCode; 'passport' is reserved.
        CheckConstraint(
            "application_code ~ '^[a-z][a-z0-9-]{1,30}[a-z0-9]$' "
            "AND application_code <> 'passport'",
            name="application_code",
        ),
        CheckConstraint(
            "(previous_client_secret_hash IS NULL) = "
            "(previous_secret_valid_until IS NULL)",
            name="previous_secret",
        ),
    )
    __mapper_args__: Mapping[str, Any] = {"eager_defaults": True}

    application_id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid7
    )
    # OAuth client_id and Access Token audience.
    application_code: Mapped[str] = mapped_column(String(32), unique=True)
    application_name: Mapped[str] = mapped_column(String(100))
    application_status: Mapped[ApplicationStatus] = mapped_column(
        IntEnumType(ApplicationStatus),
        server_default=text(str(ApplicationStatus.ACTIVE.value)),
    )
    # SHA-256 of the 256-bit random secret. A fast hash is enough for random
    # secrets, and Argon2id would be too slow for per-request authentication.
    client_secret_hash: Mapped[bytes]
    # Hash of the secret replaced by the last rotation.
    previous_client_secret_hash: Mapped[bytes | None]
    # Proposed: 24 hours after rotation.
    previous_secret_valid_until: Mapped[datetime | None]
    secret_rotated_at: Mapped[datetime] = mapped_column(server_default=func.now())
    # Allowed SSO callback URIs (API field sso_redirect_uris); exact match only.
    bff_redirect_uris: Mapped[list[str]] = mapped_column(
        ARRAY(Text), server_default=text("'{}'")
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )
    # No FK: withdrawal deletes the user row, and applications must outlive it.
    created_by: Mapped[uuid.UUID]
    updated_by: Mapped[uuid.UUID]
    # Optional link to a record in another system: its ID and where it lives.
    external_id: Mapped[str | None] = mapped_column(String(50))
    external_source: Mapped[str | None] = mapped_column(String(50))


class TenantApplication(Base):
    """Whether a tenant's members may use an application.

    No row means the contract's not_enabled. The row is created on the first
    activation and toggled afterwards. Access checks read the current row on
    every request (FR-APP-008).
    """

    __tablename__ = "tenant_applications"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.tenant_id", ondelete="RESTRICT"), primary_key=True
    )
    # Second PK column, indexed separately for lookups by application.
    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("applications.application_id", ondelete="RESTRICT"),
        primary_key=True,
        index=True,
    )
    # API field "status".
    application_status: Mapped[ApplicationStatus] = mapped_column(
        IntEnumType(ApplicationStatus)
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    # No FK: withdrawal deletes the user row, and subscriptions must outlive it.
    created_by: Mapped[uuid.UUID]
