"""
Test data generator

USAGE: generate [-h | --help]

  -h | --help  Print this message and exit

ENVIRONMENT VARIABLES:

  APP_URL
    URL to send events
    [type: string]
    [default: http://localhost:8080/api/event]

  APP_BATCH_SIZE
    Number of events in one request
    [type: int]
    [default: 10]

  APP_ITERATIONS
    Number of requests to send
    [type: int]
    [default: 1000]

  APP_DELAY_S
    Delay between requests in seconds
    [type: float]
    [default: 0.2]

  APP_LOG__LEVEL
    Logging level
    [type: string]
    [default: INFO]
"""
import asyncio
import json
import logging
import random
from datetime import datetime, timezone
from string import ascii_letters, digits

import aiohttp
from pydantic import HttpUrl
from pydantic_settings import BaseSettings

from audit_svc.help import help_message
from audit_svc.settings import SETTINGS_CONFIG, LoggingSettings

ALPHABET = ascii_letters + digits
EVENTS = ["UserLogin", "UserCreated", "UserLogout"]
APPLICATIONS = ["grease_monkey", "cauliflower", "death_star"]


class Settings(BaseSettings):
    model_config = SETTINGS_CONFIG

    log: LoggingSettings = LoggingSettings()

    url: HttpUrl = HttpUrl("http://localhost:8080/api/event")
    batch_size: int = 10
    iterations: int = 1000
    delay_s: float = 0.2


async def run(settings: Settings):
    async with aiohttp.ClientSession() as session:
        for i in range(1, 1 + settings.iterations):
            logging.info("batch %d / %d", i, settings.iterations)
            batch = generate_events(settings.batch_size)
            r = await session.post(str(settings.url), data=json.dumps(batch))
            logging.info("batch %d response status: %d", i, r.status)
            await asyncio.sleep(settings.delay_s)


def generate_events(batch_size: int):
    application_name = random.choice(APPLICATIONS)
    now = datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()
    result = []
    for _ in range(batch_size):
        result.append(
            {
                "event_ts": now,
                "application_name": application_name,
                "event_kind": random.choice(EVENTS),
                "payload": {"username": f"user_{random_word()}"},
            }
        )
    return result


def random_word():
    return "".join(random.choice(ALPHABET) for _ in range(8))


def main():
    help_message(__doc__)
    settings = Settings()  # type:ignore
    settings.log.configure()
    asyncio.run(run(settings))


if __name__ == "__main__":
    main()
