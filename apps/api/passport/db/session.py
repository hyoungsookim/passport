"""Async database engine and session factory."""

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def create_engine(url: str, *, pool_size: int, pool_timeout: float) -> AsyncEngine:
    return create_async_engine(url, pool_size=pool_size, pool_timeout=pool_timeout)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    # Async sessions cannot lazy-load expired attributes after commit.
    return async_sessionmaker(engine, expire_on_commit=False)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    # No auto-commit: services own transactions; close() rolls back what is left.
    async with request.app.state.session_factory() as session:
        yield session
