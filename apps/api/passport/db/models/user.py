"""User models (DB_MODEL.md 4.1)."""

import uuid
from collections.abc import Mapping
from datetime import datetime
from enum import IntEnum
from typing import Any

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint, false, func, text
from sqlalchemy.orm import Mapped, mapped_column

from passport.db.base import Base, IntEnumType


class UserStatus(IntEnum):
    PENDING_VERIFICATION = 1
    ACTIVE = 2
    SUSPENDED = 3
    DEACTIVATED = 4


class PasswordAlgorithm(IntEnum):
    ARGON2ID = 1


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    user_status: Mapped[UserStatus] = mapped_column(
        IntEnumType(UserStatus),
        server_default=text(str(UserStatus.PENDING_VERIFICATION.value)),
    )
    is_system: Mapped[bool] = mapped_column(server_default=false())
    is_platform_admin: Mapped[bool] = mapped_column(server_default=false())
    user_email: Mapped[str] = mapped_column(String(254), unique=True)
    display_name: Mapped[str] = mapped_column(String(50))
    # Column name kept as specified in DB_MODEL.md.
    fist_name: Mapped[str | None] = mapped_column(String(50))
    last_name: Mapped[str | None] = mapped_column(String(50))
    email_verified_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )
    external_id: Mapped[str | None] = mapped_column(String(50))
    external_source: Mapped[str | None] = mapped_column(String(50))
    version: Mapped[int] = mapped_column(server_default=text("1"))

    # eager_defaults: RETURNING the onupdate timestamp; async sessions cannot lazy-load it.
    __mapper_args__: Mapping[str, Any] = {
        "version_id_col": version,
        "eager_defaults": True,
    }


class UserSecurity(Base):
    __tablename__ = "user_securities"
    __mapper_args__: Mapping[str, Any] = {"eager_defaults": True}

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True
    )
    password_hash: Mapped[str | None] = mapped_column(Text)
    password_changed_at: Mapped[datetime | None]
    password_algorithm: Mapped[PasswordAlgorithm | None] = mapped_column(
        IntEnumType(PasswordAlgorithm)
    )
    must_change_password: Mapped[bool] = mapped_column(server_default=false())
    failed_login_count: Mapped[int] = mapped_column(server_default=text("0"))
    last_failed_login_at: Mapped[datetime | None]
    last_login_at: Mapped[datetime | None]
    locked_until: Mapped[datetime | None]
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )


class Identity(Base):
    __tablename__ = "identities"
    __table_args__ = (
        UniqueConstraint("issuer", "subject", name="uq_identities_issuer_subject"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), index=True
    )
    issuer: Mapped[str] = mapped_column(String(2048))
    subject: Mapped[str] = mapped_column(String(255))
    # tenants / tenant_oidc_configurations are defined with DB_MODEL.md 4.2.
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="RESTRICT")
    )
    oidc_config_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenant_oidc_configurations.id", ondelete="RESTRICT")
    )
    linked_at: Mapped[datetime] = mapped_column(server_default=func.now())
    last_used_at: Mapped[datetime | None]


class EmailVerificationToken(Base):
    __tablename__ = "email_verification_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True
    )
    token_hash: Mapped[bytes] = mapped_column(unique=True)
    expires_at: Mapped[datetime]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
