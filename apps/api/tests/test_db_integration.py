"""Runs against the database configured by config.json and PASSPORT_DB_* env."""

from typing import Annotated

import pytest
import pytest_asyncio
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.pool import AsyncAdaptedQueuePool

from passport.db.session import create_engine, create_session_factory, get_session
from passport.main import create_app
from passport.settings.config import SettingsError, database_url, load_settings

pytestmark = pytest.mark.asyncio


@pytest.fixture
def database():
    try:
        database = load_settings().database
        url = database_url(database, "PASSPORT_DB_USERNAME", "PASSPORT_DB_PASSWORD")
    except SettingsError as e:
        pytest.skip(f"database not configured: {e}")
    return database, url


@pytest_asyncio.fixture
async def client(database):
    database, url = database
    # One pooled connection, so every request below reuses the same backend.
    engine = create_engine(url, pool_size=1, pool_timeout=database.pool_timeout)
    app = FastAPI()
    app.state.session_factory = create_session_factory(engine)
    Session = Annotated[AsyncSession, Depends(get_session)]

    @app.post("/probe")
    async def create_probe(session: Session, commit: bool = False, fail: bool = False):
        await session.execute(text("CREATE TEMP TABLE probe (x int)"))
        if commit:
            await session.commit()
        if fail:
            raise RuntimeError

    @app.get("/probe")
    async def probe(session: Session):
        return await session.scalar(
            text("SELECT to_regclass('pg_temp.probe') IS NOT NULL")
        )

    @app.get("/pid")
    async def pid(session: Session):
        return await session.scalar(text("SELECT pg_backend_pid()"))

    transport = ASGITransport(app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        yield c
    await engine.dispose()


@pytest.mark.parametrize(("params", "status"), [({}, 200), ({"fail": True}, 500)])
async def test_uncommitted_work_is_rolled_back_when_request_ends(
    client, params, status
):
    pid = (await client.get("/pid")).json()
    response = await client.post("/probe", params=params)

    assert response.status_code == status
    assert (await client.get("/probe")).json() is False
    assert (await client.get("/pid")).json() == pid


async def test_committed_work_persists_after_request_ends(client):
    pid = (await client.get("/pid")).json()
    response = await client.post("/probe", params={"commit": True})

    assert response.status_code == 200
    assert (await client.get("/probe")).json() is True
    assert (await client.get("/pid")).json() == pid


async def test_lifespan_opens_pool_and_disposes_it_on_shutdown(database):
    app = create_app()

    async with app.router.lifespan_context(app):
        engine = app.state.session_factory.kw["bind"]
        async with app.state.session_factory() as session:
            assert await session.scalar(text("SELECT 1")) == 1
        assert isinstance(engine.pool, AsyncAdaptedQueuePool)
        assert engine.pool.checkedin() == 1

    assert isinstance(engine.pool, AsyncAdaptedQueuePool)
    assert engine.pool.checkedin() == 0


async def test_api_account_cannot_change_schema(database):
    _, url = database
    engine = create_engine(url, pool_size=1, pool_timeout=5)
    try:
        async with engine.connect() as connection:
            with pytest.raises(ProgrammingError, match="permission denied"):
                await connection.execute(text("CREATE TABLE public.denied (x int)"))
    finally:
        await engine.dispose()
