/*
    Create papyrus_user role for application-level database access
    through API services.

    실행 방법: superuser 로 대상 데이터베이스(papyrus)에 접속해 실행한다.
    실행 순서: create_owner.sql → create_user.sql → alembic upgrade head

    여러 번 실행해도 안전하고, 마이그레이션 전후 어느 시점에 실행해도 된다.
    - 마이그레이션 전: 기본 권한(default privileges)이 이후 papyrus_owner 가
      만드는 스키마와 테이블에 권한을 부여한다.
    - 마이그레이션 후: 이미 만들어진 스키마와 테이블에 권한을 직접 부여한다.
      기본 권한은 이후에 만들어지는 객체에만 적용되고 소급되지 않기 때문이다.

    데이터베이스를 drop 하고 다시 만들었다면 이 스크립트를 다시 실행해야 한다.
    기본 권한은 데이터베이스 단위(pg_default_acl)로 저장되어 함께 사라진다.

	WARNING: Make sure to change the password in production.
	         psql 의 \password papyrus_user 로 바꾼다. ALTER ROLE ... PASSWORD 에
	         평문을 쓰면 서버 로그와 psql history 에 남는다.
*/

-- 롤은 클러스터 단위다. 데이터베이스를 다시 만들어도 남아 있으므로 없을 때만 만든다.
-- 이미 있는 롤의 속성과 비밀번호는 바꾸지 않는다.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT FROM pg_catalog.pg_roles WHERE rolname = 'passport_user'
    ) THEN
        CREATE ROLE passport_user
        WITH
            LOGIN
            NOSUPERUSER
            NOCREATEDB
            NOCREATEROLE
            NOINHERIT
            NOREPLICATION
            NOBYPASSRLS
        CONNECTION LIMIT -1
        PASSWORD 'passport_user';
    END IF;
END
$$;

-- 아래는 데이터베이스 단위 설정이다. 데이터베이스를 다시 만들면 사라진다.
REVOKE CONNECT ON DATABASE passport FROM PUBLIC;

GRANT CONNECT ON DATABASE passport TO passport_user;

-- 이후 passport_owner 가 만들 객체(마이그레이션)에 적용되는 기본 권한.
ALTER DEFAULT PRIVILEGES FOR ROLE passport_owner
GRANT USAGE ON SCHEMAS TO passport_user;

ALTER DEFAULT PRIVILEGES FOR ROLE passport_owner
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO passport_user;

-- 이미 만들어진 객체. 기본 권한과 같은 범위(passport_owner 소유 스키마)에 같은
-- 권한을 준다. 마이그레이션 전이면 대상 스키마가 없어 아무 일도 하지 않는다.
DO $$
DECLARE
    target_schema name;
BEGIN
    FOR target_schema IN
        SELECT nspname
        FROM pg_catalog.pg_namespace
        WHERE nspowner = 'passport_owner'::regrole
    LOOP
        EXECUTE format(
            'GRANT USAGE ON SCHEMA %I TO passport_user',
            target_schema
        );
        EXECUTE format(
            'GRANT SELECT, INSERT, UPDATE, DELETE '
            'ON ALL TABLES IN SCHEMA %I TO passport_user',
            target_schema
        );
    END LOOP;
END
$$;
