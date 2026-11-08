"""ASGI application entry point."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from passport.core.logging import queue_logging
from passport.db.session import create_engine, create_session_factory
from passport.settings.config import database_url, load_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    database = load_settings().database
    url = database_url(database, "PASSPORT_DB_USERNAME", "PASSPORT_DB_PASSWORD")
    with queue_logging():
        engine = create_engine(
            url, pool_size=database.pool_size, pool_timeout=database.pool_timeout
        )
        app.state.session_factory = create_session_factory(engine)
        try:
            yield
        finally:
            await engine.dispose()


def create_app() -> FastAPI:
    return FastAPI(title="Passport API", version="0.1.0", lifespan=lifespan)


app = create_app()
