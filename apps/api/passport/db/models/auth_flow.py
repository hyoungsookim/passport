"""Authentication flow models: one-time values (DB_MODEL.md 4.5).

OIDC callbacks and SSO codes are found by hash and consumed exactly once with
UPDATE ... SET consumed_at = now() WHERE ... AND consumed_at IS NULL AND
expires_at > now() RETURNING ...; the consumption and the business change it
allows commit in one transaction. Raw values are never stored, only SHA-256
hashes or ciphertexts.
"""

import uuid
from datetime import datetime
from enum import IntEnum

from sqlalchemy import CheckConstraint, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from passport.db.base import Base, IntEnumType


class OidcIntent(IntEnum):
    """Purpose of an external OIDC flow."""

    LOGIN = 1  # Log in, possibly creating the account.
    LINK = 2  # Link an external identity to the logged-in account.
    REAUTH = 3  # Reauthenticate the logged-in user for a sensitive action.


class AuthSession(Base):
    """One short-lived external OIDC flow, from start to identity link ticket.

    Ties state, nonce and PKCE to the tenant, OIDC configuration and the
    browser that started the flow, so the callback can be verified. When an
    identity link is needed, the same row then records the verified external
    identity and a one-time link ticket. Callback and ticket are consumed and
    expire independently.

    - Browser binding: the BFF start path stores a 256-bit random value in a
      per-flow __Host-passport_oidc_<id> cookie. The callback compares its
      hash before consuming anything and rejects a missing or wrong cookie.
    - Start locks the tenant and configuration rows (DB_MODEL.md 5.4) and
      creates the row for the enabled configuration. The callback verifies
      with the provider first, then takes the same locks, re-reads the row
      and rechecks that it exists, is unconsumed and unexpired, and that the
      configuration is still enabled.
    - link_required (LOGIN) or link_ready (LINK) fills the ticket fields in
      the transaction that consumes the callback. At most one ticket per
      flow, never reissued on callback replay; REAUTH never gets one.
    - Ticket use: UPDATE ... SET ticket_consumed_at = now() WHERE
      ticket_hash = :ticket_hash AND consumed_at IS NOT NULL AND
      ticket_consumed_at IS NULL AND ticket_expires_at > now() RETURNING ...,
      committed with the user_identities insert. The callback's expires_at
      does not limit a valid ticket.
    - A trust change deletes this configuration's rows whose callback is
      unconsumed or whose ticket is issued but unused. The cleanup job keeps
      a row while its ticket is still valid (DB_MODEL.md 9.1).
    """

    __tablename__ = "auth_sessions"
    __table_args__ = (
        CheckConstraint(
            "octet_length(browser_binding_hash) = 32", name="browser_binding_hash"
        ),
        # LOGIN starts without a session; LINK and REAUTH belong to one.
        CheckConstraint(
            f"(intent = {OidcIntent.LOGIN.value}) = (user_session_id IS NULL)",
            name="intent",
        ),
    )

    auth_session_id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid7
    )
    # SHA-256 of the OAuth "state"; the callback finds the flow by it.
    state_hash: Mapped[bytes] = mapped_column(unique=True)
    # SHA-256 of the flow's browser cookie value.
    browser_binding_hash: Mapped[bytes]
    # SHA-256 of the nonce, compared with the ID Token "nonce".
    nonce_hash: Mapped[bytes]
    # Encrypted PKCE verifier, needed again for the provider token exchange.
    pkce_verifier_ciphertext: Mapped[bytes]
    # Must match the tenant_id in the callback path (FR-OIDC-012).
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.tenant_id", ondelete="RESTRICT")
    )
    config_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenant_oidc_configurations.config_id", ondelete="RESTRICT")
    )
    intent: Mapped[OidcIntent] = mapped_column(IntEnumType(OidcIntent))
    # Registered portal completion URI.
    return_to: Mapped[str] = mapped_column(String(2048))
    # Session a LINK or REAUTH flow belongs to; deleted with it.
    user_session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_sessions.user_session_id", ondelete="CASCADE")
    )
    # Callback expiry. Proposed: 10 minutes after start.
    expires_at: Mapped[datetime]
    # When the callback was consumed; separate from ticket consumption.
    consumed_at: Mapped[datetime | None]
    # --- Link ticket fields (see ck_auth_sessions_ticket) ---
    # SHA-256 of the link ticket.
    ticket_hash: Mapped[bytes | None] = mapped_column(unique=True)
    # Verified external identity the ticket will link.
    issuer: Mapped[str | None] = mapped_column(String(2048))
    subject: Mapped[str | None] = mapped_column(String(255))
    ticket_issued_at: Mapped[datetime | None]
    # Proposed: 10 minutes after issue, independent of expires_at.
    ticket_expires_at: Mapped[datetime | None]
    # When the ticket was used; NULL while unused.
    ticket_consumed_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class AuthorizationCode(Base):
    """Short-lived one-time authorization code for SSO between services.

    Binds the code to the client, redirect URI, original user session, tenant
    and PKCE challenge, so the server-to-server exchange can check them. The
    exchange records the refresh token family it created; if the consumed
    code is presented again, that family is revoked.
    """

    __tablename__ = "authorization_codes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    # SHA-256 of the code. The raw code is never stored.
    code_hash: Mapped[bytes] = mapped_column(unique=True)
    # Application code that requested the code.
    client_id: Mapped[str] = mapped_column(String(32))
    redirect_uri: Mapped[str] = mapped_column(String(2048))
    # Original user session; deleted with it.
    user_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user_sessions.user_session_id", ondelete="CASCADE")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.tenant_id", ondelete="RESTRICT")
    )
    # PKCE S256 code challenge.
    code_challenge: Mapped[str] = mapped_column(String(128))
    # Proposed: 60 seconds after issue.
    expires_at: Mapped[datetime]
    consumed_at: Mapped[datetime | None]
    # Family created by the exchange; revoked if the code is replayed.
    refresh_family_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("client_sessions.client_session_id", ondelete="CASCADE")
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
