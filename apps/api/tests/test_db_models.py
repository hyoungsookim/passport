import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from passport.db.base import Base, IntEnumType
from passport.db.models import (
    EmailVerificationToken,
    Identity,
    PasswordAlgorithm,
    User,
    UserSecurity,
    UserStatus,
)

DIALECT = postgresql.dialect()


def ddl(model):
    return " ".join(str(CreateTable(model.__table__).compile(dialect=DIALECT)).split())


@pytest.mark.parametrize(
    ("enum", "keys"),
    [
        (
            UserStatus,
            {"PENDING_VERIFICATION": 1, "ACTIVE": 2, "SUSPENDED": 3, "DEACTIVATED": 4},
        ),
        (PasswordAlgorithm, {"ARGON2ID": 1}),
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


def test_identities_schema():
    # Full DDL needs the 4.2 tenant tables, so check the 4.1 parts directly.
    table = Base.metadata.tables[Identity.__tablename__]

    assert {(c.name, c.nullable) for c in table.c} == {
        ("id", False),
        ("user_id", False),
        ("issuer", False),
        ("subject", False),
        ("tenant_id", False),
        ("oidc_config_id", False),
        ("linked_at", False),
        ("last_used_at", True),
    }
    assert {(fk.target_fullname, fk.ondelete) for fk in table.foreign_keys} == {
        ("users.user_id", "CASCADE"),
        ("tenants.id", "RESTRICT"),
        ("tenant_oidc_configurations.id", "RESTRICT"),
    }
    assert "uq_identities_issuer_subject" in {c.name for c in table.constraints}
    assert {i.name for i in table.indexes} == {"ix_identities_user_id"}
