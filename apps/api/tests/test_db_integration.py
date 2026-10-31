"""Runs against the database configured by config.json and PASSPORT_DB_* env."""

from typing import Annotated

import pytest
import pytest_asyncio
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from passport.db.session import create_engine, create_session_factory, get_session
from passport.settings.config import SettingsError, database_url, load_settings

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def client():
    try:
        database = load_settings().database
        url = database_url(database, "PASSPORT_DB_USERNAME", "PASSPORT_DB_PASSWORD")
    except SettingsError as e:
        pytest.skip(f"database not configured: {e}")

    # One pooled connection, so every request below reuses the same backend.
    engine = create_engine(url, pool_size=1, pool_timeout=database.pool_timeout)
    app = FastAPI()
    app.state.session_factory = create_session_factory(engine)
    Session = Annotated[AsyncSession, Depends(get_session)]

    @app.post("/probe")
    async def create_probe(commit: bool, session: Session):
        await session.execute(text("CREATE TEMP TABLE probe (x int)"))
        if commit:
            await session.commit()

    @app.get("/probe")
    async def probe(session: Session):
        return await session.scalar(
            text("SELECT to_regclass('pg_temp.probe') IS NOT NULL")
        )

    @app.get("/pid")
    async def pid(session: Session):
        return await session.scalar(text("SELECT pg_backend_pid()"))

    async with AsyncClient(transport=ASGITransport(app), base_url="http://t") as c:
        yield c
    await engine.dispose()


async def test_uncommitted_work_is_rolled_back_when_request_ends(client):
    pid = (await client.get("/pid")).json()
    response = await client.post("/probe", params={"commit": False})

    assert response.status_code == 200
    assert (await client.get("/probe")).json() is False
    assert (await client.get("/pid")).json() == pid


async def test_committed_work_persists_after_request_ends(client):
    pid = (await client.get("/pid")).json()
    response = await client.post("/probe", params={"commit": True})

    assert response.status_code == 200
    assert (await client.get("/probe")).json() is True
    assert (await client.get("/pid")).json() == pid
