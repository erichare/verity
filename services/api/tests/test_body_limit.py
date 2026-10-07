"""Streamed request limits stop reads and cannot be downgraded by a parser."""

import asyncio
import json
from dataclasses import replace

import pytest
from starlette.responses import JSONResponse

from verity_api import limits
from verity_api.body_limit import BodySizeLimitMiddleware


@pytest.mark.parametrize("headers", [[], [(b"content-length", b"1")]])
def test_actual_body_limit_stops_before_reading_remaining_chunks(monkeypatch, headers):
    monkeypatch.setattr(limits, "LIMITS", replace(limits.LIMITS, max_total_bytes=128))
    received = []
    sent = []
    chunks = iter([b"a" * 64, b"b" * 65, b"never read"])

    async def receive():
        chunk = next(chunks)
        received.append(chunk)
        return {"type": "http.request", "body": chunk, "more_body": True}

    async def send(message):
        sent.append(message)

    async def parser(scope, receive, send):
        try:
            while True:
                await receive()
        except Exception:
            await JSONResponse(status_code=400, content={"detail": "bad JSON"})(
                scope, receive, send
            )

    asyncio.run(
        BodySizeLimitMiddleware(parser)({"type": "http", "headers": headers}, receive, send)
    )
    assert len(received) == 2
    assert sent[0]["status"] == 413
    assert json.loads(sent[1]["body"]) == {"detail": "request body too large"}
