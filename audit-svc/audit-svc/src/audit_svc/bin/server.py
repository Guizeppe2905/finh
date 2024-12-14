"""
Run audit backend server

USAGE: server [-h | --help]

  -h | --help  Print this message and exit

ENVIRONMENT VARIABLES:

  APP_HOST
    Address to listen. Use `0.0.0.0` to listen to all interfaces.
    [type: string]
    [default: "0.0.0.0"]

  APP_PORT
    Port to listen on
    [type: integer]
    [default: 8080]

  APP_CONFIG
    Path to configuration file in YAML format
    [type: path]
    [default: ./config.yml]

  APP_LOG__LEVEL
    Logging level
    [type: string]
    [default: INFO]

CONFIGURATION:

    This server reads reloadable configuration entries from YAML file.
    To reload configuration call `POST /reload` endpoint

```
postgres:
    dsn: # PostgreSQL connection string. See `https://magicstack.github.io/asyncpg/current/api/index.html#connection`
```
"""
import logging
from pathlib import Path
from typing import Awaitable, Callable

import aiofiles
from aiohttp.web import Application, Request, Response, run_app
from aiohttp_prometheus_exporter.handler import metrics
from aiohttp_prometheus_exporter.middleware import prometheus_middleware_factory
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
from ruamel.yaml import YAML

from audit_svc.help import help_message
from audit_svc.routes import STATE_KEY, routes
from audit_svc.settings import SETTINGS_CONFIG, LoggingSettings, PostgresSettings
from audit_svc.state import State, StateData


class Settings(BaseSettings):
    model_config = SETTINGS_CONFIG

    log: LoggingSettings = LoggingSettings()

    host: str = "0.0.0.0"
    port: int = 8080
    config: Path = Field(default=Path("config.yml"))

    async def read_config(self):
        loader = YAML(typ="safe")
        async with aiofiles.open(self.config, encoding="utf-8") as fp:
            data = await fp.read()
        return Config.model_validate(loader.load(data))


class Config(BaseModel):
    postgres: PostgresSettings

    async def into_state_data(self) -> StateData:
        return StateData(pool=await self.postgres.into_pool())


async def on_shutdown(app: Application):
    state: StateData = app[STATE_KEY]
    await state.close()


async def create_app(settings: Settings) -> Application:
    app = Application()
    app[STATE_KEY] = State(await (await settings.read_config()).into_state_data())
    app.on_shutdown.append(on_shutdown)
    app.router.add_routes(routes)
    app.router.add_get("/metrics", metrics())
    app.router.add_get("/health", health)
    app.router.add_post("/reload", make_reloader(settings))
    app.middlewares.append(prometheus_middleware_factory(metrics_prefix="http"))  # type: ignore
    return app


async def health(_request: Request) -> Response:
    return Response(status=200)


def make_reloader(settings: Settings) -> Callable[[Request], Awaitable[Response]]:
    async def reload(request: Request) -> Response:
        logging.info("configuration reload")
        state: State = request.app[STATE_KEY]
        config = await settings.read_config()
        logging.debug("new configuration: %s", config.model_dump_json())
        await state.update(await config.into_state_data())
        return Response(status=201)

    return reload


def main():
    help_message(__doc__)
    settings = Settings()  # type: ignore
    settings.log.configure()
    logging.debug("settings: %s", settings.model_dump_json())
    run_app(create_app(settings))


if __name__ == "__main__":
    main()
