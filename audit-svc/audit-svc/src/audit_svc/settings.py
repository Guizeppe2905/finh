import logging
import sys

from pydantic import BaseModel, PostgresDsn
from pydantic_settings import SettingsConfigDict

from .postgres import Pool

SETTINGS_CONFIG = SettingsConfigDict(
    env_prefix="APP_",
    env_file=".env",
    env_file_encoding="utf-8",
    env_nested_delimiter="__",
)


class LoggingSettings(BaseModel):
    level: str = "INFO"

    def configure(self):
        logging.basicConfig(
            stream=sys.stderr,
            level=self.level,
            format="%(asctime)s - %(levelname)s : %(message)s",
        )


class PostgresSettings(BaseModel):
    dsn: PostgresDsn

    async def into_pool(self) -> Pool:
        return await Pool.make(self.dsn)
