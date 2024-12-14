from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator

import asyncpg
from readerwriterlock.rwlock_async import RWLockFairD

from .postgres import Pool


@dataclass(frozen=True)
class StateData:
    pool: Pool

    async def close(self):
        await self.pool.close()


class State:
    _lock: RWLockFairD
    _data: StateData

    def __init__(self, data: StateData) -> None:
        self._lock = RWLockFairD()
        self._data = data

    @asynccontextmanager
    async def read(self) -> AsyncIterator[StateData]:
        guard = await self._lock.gen_rlock()
        try:
            await guard.acquire()
            yield self._data
        finally:
            await guard.release()

    async def update(self, data: StateData):
        guard = await self._lock.gen_wlock()
        try:
            await guard.acquire()
            await self._data.close()
            self._data = data
        finally:
            await guard.release()

    async def close(self):
        guard = await self._lock.gen_wlock()
        try:
            await guard.acquire()
            await self._data.close()
        finally:
            await guard.release()

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[asyncpg.Connection]:
        async with self.read() as data, data.pool.acquire() as conn, conn.transaction():
            yield conn
