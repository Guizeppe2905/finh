"""
Run database migrations for audit backend server

USAGE: migrate [-h | --help]

  -h | --help  Print this message and exit

ENVIRONMENT VARIABLES:

  APP_POSTGRES__DSN
    PostgreSQL connection string. See `https://magicstack.github.io/asyncpg/current/api/index.html#connection`
    [type: string]

  APP_LOG__LEVEL
    Logging level
    [type: string]
    [default: INFO]
"""
import asyncio
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import asyncpg
from pydantic import PostgresDsn
from pydantic_settings import BaseSettings

from audit_svc.help import help_message
from audit_svc.postgres import Pool
from audit_svc.settings import SETTINGS_CONFIG, LoggingSettings, PostgresSettings

HERE = Path(__file__).parent.resolve()
SQL_DIRECTOTY = HERE.joinpath("../sql").resolve()
MIGRATION_NAME_PATTERN = re.compile(
    r"v(?P<version>[0-9]+)__(?P<name>[a-zA-Z0-9_]+).sql"
)

Q_CREATE_VERSIONS_TABLE = """
CREATE TABLE IF NOT EXISTS migration_version (
    version int8
)
"""
Q_SELECT_MAX_VERSION = """
SELECT
    version
FROM migration_version
ORDER BY version DESC
LIMIT 1
"""
Q_INSERT_VERSION = """
INSERT INTO migration_version (version)
VALUES ($1)
"""


@dataclass
class Migration:
    version: int
    name: str
    statements: List[str]


class Settings(BaseSettings):
    model_config = SETTINGS_CONFIG

    log: LoggingSettings = LoggingSettings()
    postgres: PostgresSettings


async def run(postgres_dsn: PostgresDsn, migrations: List[Migration]):
    async with Pool(postgres_dsn) as pool, pool.acquire() as conn, conn.transaction():
        current_version = await get_or_create_version(conn)
        if current_version is None:
            migrations_to_apply = migrations
        else:
            migrations_to_apply = [i for i in migrations if i.version > current_version]
        logging.info("applying %d migrations", len(migrations_to_apply))

        for m in migrations_to_apply:
            for st in m.statements:
                logging.info("executing statement: %s", st)
                await conn.execute(st)

        if migrations_to_apply:
            new_version = migrations_to_apply[-1].version
            await set_version(conn, new_version)


async def set_version(conn: asyncpg.Connection, version: int):
    await conn.execute(Q_INSERT_VERSION, version)


async def get_or_create_version(conn: asyncpg.Connection) -> Optional[int]:
    await conn.execute(Q_CREATE_VERSIONS_TABLE)
    row = await conn.fetchrow(Q_SELECT_MAX_VERSION)
    if not row:
        return None
    return int(row["version"])


def get_migrations(directory: Path) -> List[Migration]:
    result = []
    for i in os.scandir(str(directory)):
        m = MIGRATION_NAME_PATTERN.match(i.name)
        if not m:
            continue

        captures = m.groupdict()
        version = int(captures["version"])
        name = str(captures["name"])
        with Path(i.path).open(encoding="utf-8") as fp:
            statements = [j for i in fp.read().split(";") if (j := i.strip())]
        result.append(Migration(version, name, statements))
    result.sort(key=lambda x: x.version)
    return result


def main():
    help_message(__doc__)
    settings = Settings()  # type:ignore
    settings.log.configure()
    migrations = get_migrations(SQL_DIRECTOTY)
    asyncio.run(run(settings.postgres.dsn, migrations))


if __name__ == "__main__":
    main()
