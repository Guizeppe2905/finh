from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import AsyncIterator, Optional, Self

import asyncpg
from pydantic import PostgresDsn


class Pool(AbstractAsyncContextManager):
    _dsn: PostgresDsn
    _pool: Optional[asyncpg.Pool]

    def __init__(self, dsn: PostgresDsn) -> None:
        self._dsn = dsn
        self._pool = None

    async def __aenter__(self) -> Self:
        await self.initialize()
        return self

    async def __aexit__(self, _exc_type, _exc_value, _traceback):
        await self.close()

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[asyncpg.Connection]:
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            yield conn

    @staticmethod
    async def make(dsn: PostgresDsn) -> "Pool":
        pool = Pool(dsn)
        await pool.initialize()
        return pool

    async def initialize(self):
        if self._pool:
            return
        self._pool = await self._make_pool()

    async def close(self):
        if self._pool:
            await self._pool.close()
            self._pool = None

    async def _make_pool(self) -> asyncpg.Pool:
        pool = await asyncpg.create_pool(str(self._dsn), min_size=1)
        if not pool:
            raise RuntimeError("postgres pool is not initialized")
        return pool
