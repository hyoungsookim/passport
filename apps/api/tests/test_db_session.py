from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.pool import AsyncAdaptedQueuePool

from passport.db.session import create_engine, create_session_factory

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
