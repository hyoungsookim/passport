/*
    Create papyrus_owner role for database migration.

    실행 방법: superuser 로 대상 데이터베이스(papyrus)에 접속해 실행한다.
    실행 순서: create_owner.sql → create_user.sql → alembic upgrade head

    여러 번 실행해도 안전하다. 롤은 클러스터 단위라 이미 있으면 만들지 않고,
    데이터베이스 단위 권한은 매번 다시 부여한다. 데이터베이스를 drop 하고 다시
    만들었다면 이 스크립트부터 다시 실행해야 한다.

	WARNING: Make sure to change the password in production.
	         psql 의 \password papyrus_owner 로 바꾼다. ALTER ROLE ... PASSWORD 에
	         평문을 쓰면 서버 로그와 psql history 에 남는다.
*/

-- 롤은 클러스터 단위다. 데이터베이스를 다시 만들어도 남아 있으므로 없을 때만 만든다.
-- 이미 있는 롤의 속성과 비밀번호는 바꾸지 않는다.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT FROM pg_catalog.pg_roles WHERE rolname = 'passport_owner'
    ) THEN
        CREATE ROLE passport_owner
        WITH
            LOGIN
            NOSUPERUSER
            NOCREATEDB
            NOCREATEROLE
            INHERIT
            NOREPLICATION
            NOBYPASSRLS
        CONNECTION LIMIT -1
        PASSWORD 'passport_owner';
    END IF;
END
$$;

-- 아래는 데이터베이스 단위 설정이다. 데이터베이스를 다시 만들면 사라진다.
GRANT CONNECT ON DATABASE passport TO passport_owner;

GRANT CREATE ON DATABASE passport TO passport_owner;

ALTER DATABASE passport OWNER TO passport_owner;

-- 실행한 롤(superuser)이 이 데이터베이스에 만드는 객체의 기본 권한.
ALTER DEFAULT PRIVILEGES
GRANT ALL ON TABLES TO passport_owner;
ALTER DEFAULT PRIVILEGES
GRANT ALL ON SCHEMAS TO passport_owner;
