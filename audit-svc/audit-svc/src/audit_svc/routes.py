import json
import logging
from datetime import datetime
from json import JSONDecodeError
from typing import Any, List, Optional

from aiohttp.web import (
    HTTPUnprocessableEntity,
    Request,
    Response,
    RouteTableDef,
    json_response,
)
from pydantic import BaseModel, Field, RootModel, ValidationError

from .failure import inject_failure
from .metrics import EVENTS_INSERTED
from .state import State

STATE_KEY = "state"

routes = RouteTableDef()


Q_INSERT_EVENTS = """
INSERT INTO audit_event (event_ts, application_name, event_kind, payload)
VALUES ($1, $2, $3, $4)
"""
Q_SELECT_EVENTS = """
SELECT
    event_id,
    event_ts,
    application_name,
    event_kind,
    payload
FROM audit_event
ORDER BY event_id DESC
LIMIT $1
"""
Q_SELECT_EVENTS_PAGE = """
SELECT
    event_id,
    event_ts,
    application_name,
    event_kind,
    payload
FROM audit_event
WHERE
    event_id < $2
ORDER BY event_id DESC
LIMIT $1
"""


class Event(BaseModel):
    event_ts: datetime
    application_name: str = Field(max_length=126)
    event_kind: str
    payload: Any


class EventList(RootModel):
    root: List[Event]


class ListEventsPayload(BaseModel):
    next_page: Optional[int] = None
    page_size: int
    data: EventList


class ListQuery(BaseModel):
    page_token: Optional[int] = None
    page_size: int = 10


@routes.get("/api/event")
async def list_events(request: Request) -> Response:
    try:
        query = ListQuery.model_validate(request.query)
    except ValidationError as e:
        raise HTTPUnprocessableEntity(reason=str(e)) from e

    inject_failure()

    state = extract_state(request)

    async with state.transaction() as tr:
        if query.page_token:
            rows = await tr.fetch(
                Q_SELECT_EVENTS_PAGE,
                query.page_size,
                query.page_token,
            )
        else:
            rows = await tr.fetch(
                Q_SELECT_EVENTS,
                query.page_size,
            )

        if rows:
            next_page = int(rows[-1]["event_id"])
            events = EventList.model_validate([parse_row(i) for i in rows])
        else:
            next_page = None
            events = EventList.model_validate([])

    return json_response(
        status=200,
        text=ListEventsPayload(
            next_page=next_page,
            page_size=query.page_size,
            data=events,
        ).model_dump_json(),
    )


@routes.post("/api/event")
async def append_events(request: Request) -> Response:
    try:
        events = EventList.model_validate(await request.json()).root
    except (JSONDecodeError, ValidationError) as e:
        raise HTTPUnprocessableEntity(reason=str(e)) from e

    inject_failure()

    state = extract_state(request)

    logging.info("inserting %d events", len(events))
    async with state.transaction() as tr:
        await tr.executemany(
            Q_INSERT_EVENTS,
            [
                (i.event_ts, i.application_name, i.event_kind, json.dumps(i.payload))
                for i in events
            ],
        )

    for i in events:
        EVENTS_INSERTED.labels(i.application_name).inc()

    return Response(status=201)


def parse_row(row):
    row = dict(row)
    row["payload"] = json.loads(row["payload"])
    return row


def extract_state(request: Request) -> State:
    return request.app[STATE_KEY]
