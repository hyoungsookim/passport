import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from passport.db.base import Base, IntEnumType
from passport.db.models import (
    Application,
    ApplicationStatus,
    AuthenticationMethod,
    AuthorizationCode,
    AuthSession,
    ClientSession,
    ClientType,
    EmailVerificationToken,
    Identity,
    LoginEndReason,
    MembershipRemovalReason,
    MembershipStatus,
    OidcBindingKind,
    OidcConfigurationStatus,
    OidcIntent,
    OidcProviderType,
    OidcValidationError,
    OidcValidationStatus,
    PasswordAlgorithm,
    ReauthenticationMethod,
    RefreshToken,
    SessionBinding,
    SigningAlgorithm,
    SigningKey,
    Tenant,
    TenantApplication,
    TenantMembership,
    TenantOidcConfiguration,
    TenantRole,
    TenantStatus,
    User,
    UserSecurity,
    UserSession,
    UserStatus,
)

DIALECT = postgresql.dialect()


def ddl(model):
    table = Base.metadata.tables[model.__tablename__]
    statements = [CreateTable(table)] + [
        CreateIndex(index) for index in sorted(table.indexes, key=lambda i: i.name)
    ]
    return " ; ".join(
        " ".join(str(s.compile(dialect=DIALECT)).split()) for s in statements
    )


@pytest.mark.parametrize(
    ("enum", "keys"),
    [
        (
            UserStatus,
            {"PENDING_VERIFICATION": 1, "ACTIVE": 2, "SUSPENDED": 3, "DEACTIVATED": 4},
        ),
        (PasswordAlgorithm, {"ARGON2ID": 1}),
        (TenantStatus, {"ACTIVE": 1, "SUSPENDED": 2, "DEACTIVATED": 3}),
        (OidcProviderType, {"KEYCLOAK": 1, "AUTH0": 2}),
        (OidcConfigurationStatus, {"ENABLED": 1, "DISABLED": 2}),
        (OidcValidationStatus, {"OK": 1, "FAILED": 2}),
        (
            OidcValidationError,
            {
                "DISCOVERY_UNREACHABLE": 1,
                "ISSUER_MISMATCH": 2,
                "JWKS_UNREACHABLE": 3,
                "INVALID_CLIENT": 4,
                "UNSUPPORTED_LIFECYCLE_BINDING": 5,
            },
        ),
        (TenantRole, {"ADMIN": 1, "MEMBER": 2}),
        (MembershipStatus, {"ACTIVE": 2, "SUSPENDED": 3, "REMOVED": 4}),
        (MembershipRemovalReason, {"ADMIN_REMOVED": 1}),
        (ApplicationStatus, {"ACTIVE": 1, "INACTIVE": 2}),
        (AuthenticationMethod, {"LOCAL": 1, "OIDC": 2}),
        (ClientType, {"WEB": 1, "NATIVE": 2}),
        (ReauthenticationMethod, {"PASSWORD": 1, "OIDC": 2}),
        (
            LoginEndReason,
            {
                "LOGOUT": 1,
                "LOGOUT_ALL": 2,
                "PASSWORD_CHANGED": 3,
                "ACCOUNT_INACTIVE": 4,
                "REFRESH_REUSE": 5,
                "OIDC_TRUST_CHANGED": 6,
                "EXTERNAL_ACCOUNT_BLOCKED": 7,
                "PROVIDER_LOGOUT": 8,
                "EXTERNAL_TOKEN_REVOKED": 9,
                "RESTORE": 11,
            },
        ),
        (OidcBindingKind, {"SESSION": 1, "TOKEN": 2}),
        (SigningAlgorithm, {"ES256": 1}),
        (OidcIntent, {"LOGIN": 1, "LINK": 2, "REAUTH": 3}),
    ],
)
def test_enum_keys_match_db_model(enum, keys):
    assert {m.name: m.value for m in enum} == keys


def test_int_enum_type_converts_between_enum_and_key():
    column_type = IntEnumType(UserStatus)

    assert column_type.process_bind_param(UserStatus.ACTIVE, DIALECT) == 2
    assert column_type.process_result_value(2, DIALECT) is UserStatus.ACTIVE
    assert column_type.process_bind_param(None, DIALECT) is None
    assert column_type.process_result_value(None, DIALECT) is None


@pytest.mark.parametrize("key", [0, 5])
def test_int_enum_type_rejects_unknown_key(key):
    column_type = IntEnumType(UserStatus)

    with pytest.raises(ValueError):
        column_type.process_result_value(key, DIALECT)
    with pytest.raises(ValueError):
        column_type.process_bind_param(key, DIALECT)


def test_users_ddl():
    assert ddl(User) == (
        "CREATE TABLE users ( "
        "user_id UUID NOT NULL, "
        "user_status SMALLINT DEFAULT 1 NOT NULL, "
        "is_system BOOLEAN DEFAULT false NOT NULL, "
        "is_platform_admin BOOLEAN DEFAULT false NOT NULL, "
        "user_email VARCHAR(254) NOT NULL, "
        "display_name VARCHAR(50) NOT NULL, "
        "fist_name VARCHAR(50), "
        "last_name VARCHAR(50), "
        "email_verified_at TIMESTAMP WITH TIME ZONE, "
        "created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, "
        "updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, "
        "external_id VARCHAR(50), "
        "external_source VARCHAR(50), "
        "CONSTRAINT pk_users PRIMARY KEY (user_id), "
        "CONSTRAINT uq_users_user_email UNIQUE (user_email) )"
    )
    assert User.__mapper__.version_id_col is None


def test_user_securities_ddl():
    assert ddl(UserSecurity) == (
        "CREATE TABLE user_securities ( "
        "user_id UUID NOT NULL, "
        "password_hash TEXT, "
        "password_changed_at TIMESTAMP WITH TIME ZONE, "
        "password_algorithm SMALLINT, "
        "must_change_password BOOLEAN DEFAULT false NOT NULL, "
        "failed_login_count INTEGER DEFAULT 0 NOT NULL, "
        "last_failed_login_at TIMESTAMP WITH TIME ZONE, "
        "last_login_at TIMESTAMP WITH TIME ZONE, "
        "locked_until TIMESTAMP WITH TIME ZONE, "
        "updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, "
        "CONSTRAINT pk_user_securities PRIMARY KEY (user_id), "
        "CONSTRAINT fk_user_securities_user_id_users FOREIGN KEY(user_id) "
        "REFERENCES users (user_id) ON DELETE CASCADE )"
    )


def test_email_verification_tokens_ddl():
    assert ddl(EmailVerificationToken) == (
        "CREATE TABLE email_verification_tokens ( "
        "user_id UUID NOT NULL, "
        "token_hash BYTEA NOT NULL, "
        "expires_at TIMESTAMP WITH TIME ZONE NOT NULL, "
        "created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, "
        "CONSTRAINT pk_email_verification_tokens PRIMARY KEY (user_id), "
        "CONSTRAINT fk_email_verification_tokens_user_id_users FOREIGN KEY(user_id) "
        "REFERENCES users (user_id) ON DELETE CASCADE, "
        "CONSTRAINT uq_email_verification_tokens_token_hash UNIQUE (token_hash) )"
    )


def test_user_identities_ddl():
    assert ddl(Identity) == (
        "CREATE TABLE user_identities ( "
        "identity_id UUID NOT NULL, "
        "user_id UUID NOT NULL, "
        "issuer VARCHAR(2048) NOT NULL, "
        "subject VARCHAR(255) NOT NULL, "
        "tenant_id UUID NOT NULL, "
        "config_id UUID NOT NULL, "
        "linked_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, "
        "last_used_at TIMESTAMP WITH TIME ZONE, "
        "CONSTRAINT pk_user_identities PRIMARY KEY (identity_id), "
        "CONSTRAINT uq_user_identities_issuer_subject UNIQUE (issuer, subject), "
        "CONSTRAINT fk_user_identities_user_id_users FOREIGN KEY(user_id) "
        "REFERENCES users (user_id) ON DELETE CASCADE, "
        "CONSTRAINT fk_user_identities_tenant_id_tenants FOREIGN KEY(tenant_id) "
        "REFERENCES tenants (tenant_id) ON DELETE RESTRICT, "
        "CONSTRAINT fk_user_identities_config_id_tenant_oidc_configurations "
        "FOREIGN KEY(config_id) REFERENCES tenant_oidc_configurations (config_id) "
        "ON DELETE RESTRICT ) ; "
        "CREATE INDEX ix_user_identities_user_id ON user_identities (user_id)"
    )


def test_tenants_ddl():
    assert ddl(Tenant) == (
        "CREATE TABLE tenants ( "
        "tenant_id UUID NOT NULL, "
        "tenant_code VARCHAR(32) NOT NULL, "
        "is_system BOOLEAN DEFAULT false NOT NULL, "
        "tenant_name VARCHAR(100) NOT NULL, "
        "tenant_status SMALLINT DEFAULT 1 NOT NULL, "
        "tenant_description VARCHAR(500), "
        "created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, "
        "updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, "
        "created_by UUID NOT NULL, "
        "updated_by UUID NOT NULL, "
        "external_id VARCHAR(50), "
        "external_source VARCHAR(50), "
        "CONSTRAINT pk_tenants PRIMARY KEY (tenant_id), "
        "CONSTRAINT uq_tenants_tenant_code UNIQUE (tenant_code) )"
    )


def test_tenant_oidc_configurations_ddl():
    assert ddl(TenantOidcConfiguration) == (
        "CREATE TABLE tenant_oidc_configurations ( "
        "config_id UUID NOT NULL, "
        "tenant_id UUID NOT NULL, "
        "provider_type SMALLINT NOT NULL, "
        "display_name VARCHAR(100) NOT NULL, "
        "issuer VARCHAR(2048) NOT NULL, "
        "client_id VARCHAR(255) NOT NULL, "
        "client_secret_ciphertext BYTEA NOT NULL, "
        "scopes TEXT[] DEFAULT '{openid,email,profile}' NOT NULL, "
        "config_status SMALLINT NOT NULL, "
        "last_validation_status SMALLINT NOT NULL, "
        "last_validation_checked_at TIMESTAMP WITH TIME ZONE NOT NULL, "
        "last_validation_error_code SMALLINT, "
        "created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, "
        "updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, "
        "CONSTRAINT pk_tenant_oidc_configurations PRIMARY KEY (config_id), "
        "CONSTRAINT uq_tenant_oidc_configurations_tenant_id UNIQUE (tenant_id), "
        "CONSTRAINT fk_tenant_oidc_configurations_tenant_id_tenants "
        "FOREIGN KEY(tenant_id) REFERENCES tenants (tenant_id) ON DELETE RESTRICT )"
    )


def test_tenant_memberships_ddl():
    assert ddl(TenantMembership) == (
        "CREATE TABLE tenant_memberships ( "
        "membership_id UUID NOT NULL, "
        "tenant_id UUID NOT NULL, "
        "user_id UUID NOT NULL, "
        "role_in_tenant SMALLINT DEFAULT 2 NOT NULL, "
        "membership_status SMALLINT DEFAULT 2 NOT NULL, "
        "joined_at TIMESTAMP WITH TIME ZONE, "
        "removed_at TIMESTAMP WITH TIME ZONE, "
        "removed_reason SMALLINT, "
        "created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, "
        "updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, "
        "CONSTRAINT pk_tenant_memberships PRIMARY KEY (membership_id), "
        "CONSTRAINT fk_tenant_memberships_tenant_id_tenants FOREIGN KEY(tenant_id) "
        "REFERENCES tenants (tenant_id) ON DELETE RESTRICT, "
        "CONSTRAINT fk_tenant_memberships_user_id_users FOREIGN KEY(user_id) "
        "REFERENCES users (user_id) ON DELETE CASCADE ) ; "
        "CREATE INDEX ix_tenant_memberships_tenant_id_membership_status "
        "ON tenant_memberships (tenant_id, membership_status) ; "
        "CREATE INDEX ix_tenant_memberships_user_id ON tenant_memberships (user_id) ; "
        "CREATE UNIQUE INDEX uq_tenant_memberships_tenant_user "
        "ON tenant_memberships (tenant_id, user_id) WHERE membership_status <> 4"
    )


def test_applications_ddl():
    assert ddl(Application) == (
        "CREATE TABLE applications ( "
        "application_id UUID NOT NULL, "
        "application_code VARCHAR(32) NOT NULL, "
        "application_name VARCHAR(100) NOT NULL, "
        "application_status SMALLINT DEFAULT 1 NOT NULL, "
        "client_secret_hash BYTEA NOT NULL, "
        "previous_client_secret_hash BYTEA, "
        "previous_secret_valid_until TIMESTAMP WITH TIME ZONE, "
        "secret_rotated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, "
        "bff_redirect_uris TEXT[] DEFAULT '{}' NOT NULL, "
        "created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, "
        "updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, "
        "created_by UUID NOT NULL, "
        "updated_by UUID NOT NULL, "
        "external_id VARCHAR(50), "
        "external_source VARCHAR(50), "
        "CONSTRAINT pk_applications PRIMARY KEY (application_id), "
        "CONSTRAINT ck_applications_application_code "
        "CHECK (application_code ~ '^[a-z][a-z0-9-]{1,30}[a-z0-9]$' "
        "AND application_code <> 'passport'), "
        "CONSTRAINT ck_applications_previous_secret "
        "CHECK ((previous_client_secret_hash IS NULL) = "
        "(previous_secret_valid_until IS NULL)), "
        "CONSTRAINT uq_applications_application_code UNIQUE (application_code) )"
    )


def test_tenant_applications_ddl():
    assert ddl(TenantApplication) == (
        "CREATE TABLE tenant_applications ( "
        "tenant_id UUID NOT NULL, "
        "application_id UUID NOT NULL, "
        "application_status SMALLINT NOT NULL, "
        "created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, "
        "created_by UUID NOT NULL, "
        "CONSTRAINT pk_tenant_applications PRIMARY KEY (tenant_id, application_id), "
        "CONSTRAINT fk_tenant_applications_tenant_id_tenants FOREIGN KEY(tenant_id) "
        "REFERENCES tenants (tenant_id) ON DELETE RESTRICT, "
        "CONSTRAINT fk_tenant_applications_application_id_applications "
        "FOREIGN KEY(application_id) REFERENCES applications (application_id) "
        "ON DELETE RESTRICT ) ; "
        "CREATE INDEX ix_tenant_applications_application_id "
        "ON tenant_applications (application_id)"
    )


def test_user_sessions_ddl():
    assert ddl(UserSession) == (
        "CREATE TABLE user_sessions ( "
        "user_session_id UUID NOT NULL, "
        "user_id UUID NOT NULL, "
        "auth_method SMALLINT NOT NULL, "
        "client_type SMALLINT NOT NULL, "
        "authenticated_at TIMESTAMP WITH TIME ZONE NOT NULL, "
        "expires_at TIMESTAMP WITH TIME ZONE NOT NULL, "
        "last_activity_at TIMESTAMP WITH TIME ZONE NOT NULL, "
        "tenant_id UUID, "
        "config_id UUID, "
        "identity_id UUID, "
        "reauthenticated_at TIMESTAMP WITH TIME ZONE NOT NULL, "
        "reauth_method SMALLINT NOT NULL, "
        "ended_at TIMESTAMP WITH TIME ZONE, "
        "end_reason SMALLINT, "
        "created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, "
        "CONSTRAINT pk_user_sessions PRIMARY KEY (user_session_id), "
        "CONSTRAINT ck_user_sessions_oidc "
        "CHECK (auth_method = 1 OR (tenant_id IS NOT NULL AND config_id IS NOT NULL)), "
        "CONSTRAINT fk_user_sessions_user_id_users FOREIGN KEY(user_id) "
        "REFERENCES users (user_id) ON DELETE CASCADE, "
        "CONSTRAINT fk_user_sessions_tenant_id_tenants FOREIGN KEY(tenant_id) "
        "REFERENCES tenants (tenant_id) ON DELETE RESTRICT, "
        "CONSTRAINT fk_user_sessions_config_id_tenant_oidc_configurations "
        "FOREIGN KEY(config_id) REFERENCES tenant_oidc_configurations (config_id) "
        "ON DELETE RESTRICT, "
        "CONSTRAINT fk_user_sessions_identity_id_user_identities "
        "FOREIGN KEY(identity_id) REFERENCES user_identities (identity_id) "
        "ON DELETE CASCADE ) ; "
        "CREATE INDEX ix_user_sessions_config_id ON user_sessions (config_id) "
        "WHERE ended_at IS NULL ; "
        "CREATE INDEX ix_user_sessions_expires_at ON user_sessions (expires_at) ; "
        "CREATE INDEX ix_user_sessions_identity_id ON user_sessions (identity_id) "
        "WHERE ended_at IS NULL ; "
        "CREATE INDEX ix_user_sessions_user_id ON user_sessions (user_id) "
        "WHERE ended_at IS NULL"
    )


def test_session_bindings_ddl():
    assert ddl(SessionBinding) == (
        "CREATE TABLE session_bindings ( "
        "user_session_id UUID NOT NULL, "
        "binding_kind SMALLINT NOT NULL, "
        "binding_hash BYTEA NOT NULL, "
        "created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, "
        "CONSTRAINT pk_session_bindings "
        "PRIMARY KEY (user_session_id, binding_kind, binding_hash), "
        "CONSTRAINT ck_session_bindings_hash CHECK (octet_length(binding_hash) = 32), "
        "CONSTRAINT fk_session_bindings_user_session_id_user_sessions "
        "FOREIGN KEY(user_session_id) REFERENCES user_sessions (user_session_id) "
        "ON DELETE CASCADE ) ; "
        "CREATE INDEX ix_session_bindings_binding_kind_binding_hash "
        "ON session_bindings (binding_kind, binding_hash)"
    )


def test_client_sessions_ddl():
    assert ddl(ClientSession) == (
        "CREATE TABLE client_sessions ( "
        "client_session_id UUID NOT NULL, "
        "user_session_id UUID NOT NULL, "
        "client_id VARCHAR(32) NOT NULL, "
        "revoked_at TIMESTAMP WITH TIME ZONE, "
        "session_id UUID, "
        "session_hash BYTEA, "
        "refresh_token_ciphertext BYTEA, "
        "tenant_id UUID, "
        "access_token_ciphertext BYTEA, "
        "access_token_expires_at TIMESTAMP WITH TIME ZONE, "
        "created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, "
        "updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, "
        "CONSTRAINT pk_client_sessions PRIMARY KEY (client_session_id), "
        "CONSTRAINT ck_client_sessions_browser CHECK ("
        "(session_hash IS NULL AND session_id IS NULL "
        "AND refresh_token_ciphertext IS NULL AND tenant_id IS NULL "
        "AND access_token_ciphertext IS NULL AND access_token_expires_at IS NULL) "
        "OR (session_hash IS NOT NULL AND session_id IS NOT NULL "
        "AND refresh_token_ciphertext IS NOT NULL "
        "AND client_id = 'passport-portal' AND revoked_at IS NULL)), "
        "CONSTRAINT ck_client_sessions_access_token "
        "CHECK ((access_token_ciphertext IS NULL) = "
        "(access_token_expires_at IS NULL)), "
        "CONSTRAINT fk_client_sessions_user_session_id_user_sessions "
        "FOREIGN KEY(user_session_id) REFERENCES user_sessions (user_session_id) "
        "ON DELETE CASCADE, "
        "CONSTRAINT uq_client_sessions_session_id UNIQUE (session_id), "
        "CONSTRAINT uq_client_sessions_session_hash UNIQUE (session_hash), "
        "CONSTRAINT fk_client_sessions_tenant_id_tenants FOREIGN KEY(tenant_id) "
        "REFERENCES tenants (tenant_id) ON DELETE RESTRICT ) ; "
        "CREATE INDEX ix_client_sessions_user_session_id "
        "ON client_sessions (user_session_id)"
    )


def test_refresh_tokens_ddl():
    assert ddl(RefreshToken) == (
        "CREATE TABLE refresh_tokens ( "
        "refresh_token_id UUID NOT NULL, "
        "family_id UUID NOT NULL, "
        "token_hash BYTEA NOT NULL, "
        "issued_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, "
        "rotated_at TIMESTAMP WITH TIME ZONE, "
        "CONSTRAINT pk_refresh_tokens PRIMARY KEY (refresh_token_id), "
        "CONSTRAINT fk_refresh_tokens_family_id_client_sessions "
        "FOREIGN KEY(family_id) REFERENCES client_sessions (client_session_id) "
        "ON DELETE CASCADE, "
        "CONSTRAINT uq_refresh_tokens_token_hash UNIQUE (token_hash) ) ; "
        "CREATE UNIQUE INDEX uq_refresh_tokens_active ON refresh_tokens (family_id) "
        "WHERE rotated_at IS NULL"
    )


def test_signing_keys_ddl():
    assert ddl(SigningKey) == (
        "CREATE TABLE signing_keys ( "
        "kid VARCHAR(64) NOT NULL, "
        "alg SMALLINT DEFAULT 1 NOT NULL, "
        "public_jwk JSONB NOT NULL, "
        "private_key_ciphertext BYTEA NOT NULL, "
        "activates_at TIMESTAMP WITH TIME ZONE NOT NULL, "
        "retires_at TIMESTAMP WITH TIME ZONE NOT NULL, "
        "expires_at TIMESTAMP WITH TIME ZONE NOT NULL, "
        "revoked_at TIMESTAMP WITH TIME ZONE, "
        "created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, "
        "CONSTRAINT pk_signing_keys PRIMARY KEY (kid) )"
    )


def test_auth_sessions_ddl():
    assert ddl(AuthSession) == (
        "CREATE TABLE auth_sessions ( "
        "auth_session_id UUID NOT NULL, "
        "state_hash BYTEA NOT NULL, "
        "browser_binding_hash BYTEA NOT NULL, "
        "nonce_hash BYTEA NOT NULL, "
        "pkce_verifier_ciphertext BYTEA NOT NULL, "
        "tenant_id UUID NOT NULL, "
        "config_id UUID NOT NULL, "
        "intent SMALLINT NOT NULL, "
        "return_to VARCHAR(2048) NOT NULL, "
        "user_session_id UUID, "
        "expires_at TIMESTAMP WITH TIME ZONE NOT NULL, "
        "consumed_at TIMESTAMP WITH TIME ZONE, "
        "ticket_hash BYTEA, "
        "issuer VARCHAR(2048), "
        "subject VARCHAR(255), "
        "ticket_issued_at TIMESTAMP WITH TIME ZONE, "
        "ticket_expires_at TIMESTAMP WITH TIME ZONE, "
        "ticket_consumed_at TIMESTAMP WITH TIME ZONE, "
        "created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, "
        "CONSTRAINT pk_auth_sessions PRIMARY KEY (auth_session_id), "
        "CONSTRAINT ck_auth_sessions_browser_binding_hash "
        "CHECK (octet_length(browser_binding_hash) = 32), "
        "CONSTRAINT ck_auth_sessions_intent "
        "CHECK ((intent = 1) = (user_session_id IS NULL)), "
        "CONSTRAINT ck_auth_sessions_ticket CHECK ("
        "(ticket_hash IS NULL AND issuer IS NULL AND subject IS NULL "
        "AND ticket_issued_at IS NULL AND ticket_expires_at IS NULL "
        "AND ticket_consumed_at IS NULL) "
        "OR (ticket_hash IS NOT NULL AND issuer IS NOT NULL "
        "AND subject IS NOT NULL AND ticket_issued_at IS NOT NULL "
        "AND ticket_expires_at IS NOT NULL AND consumed_at IS NOT NULL "
        "AND intent IN (1, 2))), "
        "CONSTRAINT uq_auth_sessions_state_hash UNIQUE (state_hash), "
        "CONSTRAINT fk_auth_sessions_tenant_id_tenants FOREIGN KEY(tenant_id) "
        "REFERENCES tenants (tenant_id) ON DELETE RESTRICT, "
        "CONSTRAINT fk_auth_sessions_config_id_tenant_oidc_configurations "
        "FOREIGN KEY(config_id) REFERENCES tenant_oidc_configurations (config_id) "
        "ON DELETE RESTRICT, "
        "CONSTRAINT fk_auth_sessions_user_session_id_user_sessions "
        "FOREIGN KEY(user_session_id) REFERENCES user_sessions (user_session_id) "
        "ON DELETE CASCADE, "
        "CONSTRAINT uq_auth_sessions_ticket_hash UNIQUE (ticket_hash) ) ; "
        "CREATE INDEX ix_auth_sessions_expires_at ON auth_sessions (expires_at) ; "
        "CREATE INDEX ix_auth_sessions_user_session_id "
        "ON auth_sessions (user_session_id)"
    )


def test_authorization_codes_ddl():
    assert ddl(AuthorizationCode) == (
        "CREATE TABLE authorization_codes ( "
        "id UUID NOT NULL, "
        "code_hash BYTEA NOT NULL, "
        "client_id VARCHAR(32) NOT NULL, "
        "redirect_uri VARCHAR(2048) NOT NULL, "
        "user_session_id UUID NOT NULL, "
        "tenant_id UUID NOT NULL, "
        "code_challenge VARCHAR(128) NOT NULL, "
        "expires_at TIMESTAMP WITH TIME ZONE NOT NULL, "
        "consumed_at TIMESTAMP WITH TIME ZONE, "
        "refresh_family_id UUID, "
        "created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, "
        "CONSTRAINT pk_authorization_codes PRIMARY KEY (id), "
        "CONSTRAINT uq_authorization_codes_code_hash UNIQUE (code_hash), "
        "CONSTRAINT fk_authorization_codes_user_session_id_user_sessions "
        "FOREIGN KEY(user_session_id) REFERENCES user_sessions (user_session_id) "
        "ON DELETE CASCADE, "
        "CONSTRAINT fk_authorization_codes_tenant_id_tenants FOREIGN KEY(tenant_id) "
        "REFERENCES tenants (tenant_id) ON DELETE RESTRICT, "
        "CONSTRAINT fk_authorization_codes_refresh_family_id_client_sessions "
        "FOREIGN KEY(refresh_family_id) REFERENCES client_sessions "
        "(client_session_id) ON DELETE CASCADE ) ; "
        "CREATE INDEX ix_authorization_codes_expires_at "
        "ON authorization_codes (expires_at) ; "
        "CREATE INDEX ix_authorization_codes_user_session_id "
        "ON authorization_codes (user_session_id)"
    )
