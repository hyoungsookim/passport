from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.pool import AsyncAdaptedQueuePool

from passport.db.session import create_engine, create_session_factory, get_session

URL = "postgresql+psycopg://user:pass@localhost/passport"


def test_create_engine_applies_pool_settings():
    engine = create_engine(URL, pool_size=7, pool_timeout=3.5)

    assert isinstance(engine.pool, AsyncAdaptedQueuePool)
    assert engine.pool.size() == 7
    assert engine.pool.timeout() == 3.5


def test_session_factory_binds_engine():
    engine = create_engine(URL, pool_size=1, pool_timeout=1)
    session = create_session_factory(engine)()

    assert isinstance(session, AsyncSession)
    assert session.bind is engine
    assert session.sync_session.expire_on_commit is False


class FakeSession:
    closed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        self.closed = True


def test_get_session_yields_new_session_per_request_and_closes_it():
    app = FastAPI()
    app.state.session_factory = FakeSession
    sessions = []

    @app.get("/ok")
    def ok(session: Annotated[AsyncSession, Depends(get_session)]):
        sessions.append(session)

    @app.get("/fail")
    def fail(session: Annotated[AsyncSession, Depends(get_session)]):
        sessions.append(session)
        raise RuntimeError

    client = TestClient(app, raise_server_exceptions=False)
    client.get("/ok")
    client.get("/ok")
    assert client.get("/fail").status_code == 500

    assert len({id(s) for s in sessions}) == 3
    assert all(s.closed for s in sessions)
