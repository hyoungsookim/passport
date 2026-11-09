"""User session and token models (DB_MODEL.md 4.4).

A user session is one Passport login. Client sessions (refresh token
families), refresh tokens and external-session bindings hang off it with
ON DELETE CASCADE, so withdrawal and the session cleanup job remove them
together. Access Tokens are not stored: revocation is judged from the
user_sessions row named by the token's "sid" claim.
"""

import uuid
from collections.abc import Mapping
from datetime import datetime
from enum import IntEnum
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from passport.db.base import Base, IntEnumType


class AuthenticationMethod(IntEnum):
    """How the user authenticated to start the session."""

    LOCAL = 1  # Passport email and password.
    OIDC = 2  # External OIDC provider of a tenant.


class ClientType(IntEnum):
    """Client kind; it decides the session's absolute and idle lifetimes."""

    WEB = 1  # 8 hours absolute, 30 minutes idle.
    NATIVE = 2  # 7 days absolute, 3 days idle.


class ReauthenticationMethod(IntEnum):
    """How the user last proved their identity for sensitive operations."""

    PASSWORD = 1
    OIDC = 2


class LoginEndReason(IntEnum):
    """Why a user session ended (DB_MODEL.md 5.5). Key 10 is retired."""

    LOGOUT = 1  # Logout of this session, including SSO single logout.
    LOGOUT_ALL = 2  # Logout on every device: all of the user's sessions.
    PASSWORD_CHANGED = 3  # All of the user's sessions.
    ACCOUNT_INACTIVE = 4  # Account suspended or deactivated: all sessions.
    REFRESH_REUSE = 5  # Rotated refresh token presented again: all sessions.
    OIDC_TRUST_CHANGED = 6  # Sessions of the changed OIDC configuration.
    # External account blocked (FR-OIDC-015): every session of that identity
    # and tenant.
    EXTERNAL_ACCOUNT_BLOCKED = 7
    # Provider logout (FR-OIDC-017): only sessions bound to the verified
    # external session through session_bindings.
    PROVIDER_LOGOUT = 8
    # Token revocation (FR-OIDC-018): only sessions bound to the verified
    # revoked token through session_bindings.
    EXTERNAL_TOKEN_REVOKED = 9
    RESTORE = 11  # Backup restore ends every session.


class OidcBindingKind(IntEnum):
    """What kind of external identifier a session binding hashes."""

    SESSION = 1  # Verified external session ID ("sid").
    TOKEN = 2  # Identifier of a token whose revocation must end the session.


class SigningAlgorithm(IntEnum):
    """JWS algorithm of a signing key."""

    ES256 = 1  # Proposed default.


class UserSession(Base):
    """One Passport login: its authentication context and validity.

    The row behind the Access Token "sid" claim and the API user_session_id.
    Client sessions and SSO hang off it, and an OIDC trust change ends it
    directly (contract 3.1).

    - Passport APIs and verifyAccess load this row by PK on every request and
      check that the user exists and is usable. A missing, ended or expired
      session rejects the token. An OIDC session also needs its configuration
      to be enabled now; a session ended by a trust change is rejected however
      long the token would still be valid.
    - Expiry is computed from timestamps and never stored as a state: the
      session is expired after expires_at, or after last_activity_at plus the
      idle timeout of its client_type.
    - Ending sets ended_at and end_reason together and, in the same
      transaction, clears the browser fields of its client sessions.
    - Purged one day after ended_at or expires_at (DB_MODEL.md 9.1).
    """

    __tablename__ = "user_sessions"
    __table_args__ = (
        # OIDC sessions must record the tenant and configuration they used.
        CheckConstraint(
            f"auth_method = {AuthenticationMethod.LOCAL.value} "
            "OR (tenant_id IS NOT NULL AND config_id IS NOT NULL)",
            name="oidc",
        ),
        # Open sessions only: these drive bulk endings, which never touch
        # sessions that already ended.
        # Logout-all, password change, account block.
        Index(
            "ix_user_sessions_user_id",
            "user_id",
            postgresql_where=text("ended_at IS NULL"),
        ),
        # OIDC trust change.
        Index(
            "ix_user_sessions_config_id",
            "config_id",
            postgresql_where=text("ended_at IS NULL"),
        ),
        # External account block and provider logout.
        Index(
            "ix_user_sessions_identity_id",
            "identity_id",
            postgresql_where=text("ended_at IS NULL"),
        ),
    )

    # Access Token "sid" claim and API user_session_id.
    user_session_id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid7
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE")
    )
    auth_method: Mapped[AuthenticationMethod] = mapped_column(
        IntEnumType(AuthenticationMethod)
    )
    client_type: Mapped[ClientType] = mapped_column(IntEnumType(ClientType))
    # Token "auth_time".
    authenticated_at: Mapped[datetime]
    # Absolute expiry: login + 8 hours (web) or + 7 days (native). Token
    # refresh never extends it. Indexed for the cleanup job.
    expires_at: Mapped[datetime] = mapped_column(index=True)
    # Idle-expiry base: expired after + 30 minutes (web) or + 3 days (native).
    # Proposed: written at most once a minute to limit writes.
    last_activity_at: Mapped[datetime]
    # OIDC sessions only: the tenant and configuration used to log in.
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tenants.tenant_id", ondelete="RESTRICT")
    )
    config_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tenant_oidc_configurations.config_id", ondelete="RESTRICT")
    )
    # OIDC sessions only: the external identity used; deleted with it.
    identity_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_identities.identity_id", ondelete="CASCADE")
    )
    # Last reauthentication and its method; starts as the login time.
    reauthenticated_at: Mapped[datetime]
    reauth_method: Mapped[ReauthenticationMethod] = mapped_column(
        IntEnumType(ReauthenticationMethod)
    )
    # Set together when the session ends; NULL while it is open.
    ended_at: Mapped[datetime | None]
    end_reason: Mapped[LoginEndReason | None] = mapped_column(
        IntEnumType(LoginEndReason)
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class SessionBinding(Base):
    """Links a verified external session or token to the session it created.

    Lets provider logout and token revocation end exactly the sessions they
    name, even among several sessions of one external identity. How each
    provider's identifiers are extracted and normalized is fixed by the
    verified integration contract (FR-OIDC-017-01).

    - Look up by (binding_kind, binding_hash), then join user_sessions to
      check tenant_id, config_id and whether the session is still open.
    - End only sessions whose binding matches the identifier in a trusted
      notice. Reject and audit notices with a missing or unknown identifier,
      and never widen the scope to everything of (issuer, subject). Blocking
      an external account is separate: it ends every session of that
      identity and tenant.
    - External token values are never stored, only their hashes.
    """

    __tablename__ = "session_bindings"
    __table_args__ = (
        CheckConstraint("octet_length(binding_hash) = 32", name="hash"),
        # Lookup by external identifier; named explicitly because the naming
        # convention would only use the first column.
        Index(
            "ix_session_bindings_binding_kind_binding_hash",
            "binding_kind",
            "binding_hash",
        ),
    )

    user_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user_sessions.user_session_id", ondelete="CASCADE"),
        primary_key=True,
    )
    binding_kind: Mapped[OidcBindingKind] = mapped_column(
        IntEnumType(OidcBindingKind), primary_key=True
    )
    # SHA-256 of the verified external "sid" or the revocable token's ID.
    binding_hash: Mapped[bytes] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class ClientSession(Base):
    """One client's refresh token family in a user session, plus portal SSO.

    Each user session has one family per client (Passport portal, native app,
    each SaaS), keeping their token histories apart. For the portal
    (client_id 'passport-portal') the same row also holds the browser
    session: an opaque cookie bound to the selected tenant and to encrypted
    tokens used to relay and refresh API calls. Each SaaS manages its own
    browser session (FR-AUTH-009-02-01).

    - Rotation: SELECT ... FOR UPDATE this row, read the latest stored token,
      rotate refresh_tokens and replace the stored ciphertexts in one
      transaction. The row lock serializes concurrent refreshes.
    - The cookie is looked up by session_hash and always requires
      revoked_at IS NULL and a currently valid user session. Public IDs
      (client_session_id, session_id) never stand in for the cookie.
    - Logout, session end, family revocation and restore set every browser
      field to NULL and touch updated_at. The family and its token history
      stay until the user session is purged; withdrawal cascades them.
    """

    __tablename__ = "client_sessions"
    __table_args__ = (
        # Browser fields are all NULL, or set together on an unrevoked portal
        # family (tenant and stored Access Token may still be NULL).
        CheckConstraint(
            "(session_hash IS NULL AND session_id IS NULL "
            "AND refresh_token_ciphertext IS NULL AND tenant_id IS NULL "
            "AND access_token_ciphertext IS NULL AND access_token_expires_at IS NULL) "
            "OR (session_hash IS NOT NULL AND session_id IS NOT NULL "
            "AND refresh_token_ciphertext IS NOT NULL "
            "AND client_id = 'passport-portal' AND revoked_at IS NULL)",
            name="browser",
        ),
        CheckConstraint(
            "(access_token_ciphertext IS NULL) = (access_token_expires_at IS NULL)",
            name="access_token",
        ),
    )
    # eager_defaults: RETURNING the onupdate timestamp; async sessions cannot lazy-load it.
    __mapper_args__: Mapping[str, Any] = {"eager_defaults": True}

    # Family ID that refresh_tokens and authorization_codes refer to.
    client_session_id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid7
    )
    user_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user_sessions.user_session_id", ondelete="CASCADE"), index=True
    )
    # 'passport-portal', 'passport-native' or an Application code; the Access
    # Token client_id.
    client_id: Mapped[str] = mapped_column(String(32))
    # Revokes only this family, e.g. when an SSO code is replayed.
    revoked_at: Mapped[datetime | None]
    # --- Portal browser session fields (see ck_client_sessions_browser) ---
    # Public browser session ID (UUIDv7) assigned when the portal session is
    # created. Distinct from client_session_id.
    session_id: Mapped[uuid.UUID | None] = mapped_column(unique=True)
    # SHA-256 of the portal session cookie value.
    session_hash: Mapped[bytes | None] = mapped_column(unique=True)
    # Encrypted refresh token the portal uses for its next refresh.
    refresh_token_ciphertext: Mapped[bytes | None]
    # Tenant currently selected in the portal.
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tenants.tenant_id", ondelete="RESTRICT")
    )
    # Encrypted current Access Token held for the portal, and its expiry.
    access_token_ciphertext: Mapped[bytes | None]
    access_token_expires_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    # Touched whenever family or browser fields change.
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )


class RefreshToken(Base):
    """Hash and rotation history of issued refresh tokens.

    Shows which token of a family is current and detects reuse of rotated
    ones; reuse ends all of the user's sessions (FR-AUTH-009-07-01). Tokens
    have no expiry of their own: they live as long as the user session's
    absolute and idle expiry allow.
    """

    __tablename__ = "refresh_tokens"
    __table_args__ = (
        # At most one current (unrotated) token per family.
        Index(
            "uq_refresh_tokens_active",
            "family_id",
            unique=True,
            postgresql_where=text("rotated_at IS NULL"),
        ),
    )

    refresh_token_id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid7
    )
    family_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("client_sessions.client_session_id", ondelete="CASCADE")
    )
    # SHA-256 of the raw token. The raw token is never stored.
    token_hash: Mapped[bytes] = mapped_column(unique=True)
    issued_at: Mapped[datetime] = mapped_column(server_default=func.now())
    # When rotation replaced this token. Presenting it again is reuse.
    rotated_at: Mapped[datetime | None]


class SigningKey(Base):
    """Access Token signing key and its public verification key (FR-AUTH-008).

    Shared by every Passport process. Lifecycle: published in JWKS when
    created, signs from activates_at, stops signing at retires_at and leaves
    JWKS at expires_at. revoked_at withdraws it at once. A backup restore
    revokes every key and creates a new one, so pre-restore tokens fail
    verification (DB_MODEL.md 9.3). Rows are purged 7 days after expires_at.
    """

    __tablename__ = "signing_keys"

    # JWT header "kid" and JWKS key ID.
    kid: Mapped[str] = mapped_column(String(64), primary_key=True)
    alg: Mapped[SigningAlgorithm] = mapped_column(
        IntEnumType(SigningAlgorithm),
        server_default=text(str(SigningAlgorithm.ES256.value)),
    )
    # Public key exactly as published in JWKS.
    public_jwk: Mapped[dict[str, Any]] = mapped_column(JSONB)
    # Encrypted private key.
    private_key_ciphertext: Mapped[bytes]
    # Proposed: 24 hours after creation, so verifiers already have the key.
    activates_at: Mapped[datetime]
    # 90 days after activates_at.
    retires_at: Mapped[datetime]
    # Proposed: 24 hours after retires_at.
    expires_at: Mapped[datetime]
    # Immediate withdrawal on restore or incident.
    revoked_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
