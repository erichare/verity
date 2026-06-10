"""Reject oversized request bodies with 413 *before* they are fully parsed.

The benchmark submission endpoint accepts csv/lrs payloads; the largest
legitimate split (toolmark-v1, 167,332 pairs) needs roughly 10–20 MB, so the
default cap of 64 MiB is generous. Override with the
``VERITY_CATALOG_MAX_BODY_BYTES`` env var.

Two layers:

* a ``Content-Length`` fast path — honest oversized uploads are refused without
  reading a single body byte;
* a counting wrapper around ``receive`` — a chunked or lying upload is aborted
  as soon as the received bytes exceed the cap (the raised ``HTTPException`` is
  re-raised by FastAPI's body reader and rendered by the app's envelope
  exception handler).
"""

from __future__ import annotations

import os

from fastapi import HTTPException
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

DEFAULT_MAX_BODY_BYTES = 64 * 1024 * 1024  # 64 MiB


def _max_body_bytes() -> int:
    """The cap, re-read per request so tests (and deploys) can tune it via env."""
    raw = os.environ.get("VERITY_CATALOG_MAX_BODY_BYTES", "").strip()
    try:
        return int(raw) if raw else DEFAULT_MAX_BODY_BYTES
    except ValueError:
        return DEFAULT_MAX_BODY_BYTES


def _message(limit: int) -> str:
    return f"request body too large (limit {limit} bytes)"


class BodySizeLimitMiddleware:
    """Pure-ASGI middleware: 413 for request bodies over the configured cap."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        limit = _max_body_bytes()
        declared = _declared_content_length(scope)
        if declared is not None and declared > limit:
            response = JSONResponse(
                status_code=413,
                # The app's uniform {success, data, error, meta} envelope.
                content={"success": False, "data": None, "error": _message(limit), "meta": None},
            )
            await response(scope, receive, send)
            return

        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise HTTPException(status_code=413, detail=_message(limit))
            return message

        await self.app(scope, limited_receive, send)


def _declared_content_length(scope: Scope) -> int | None:
    for key, value in scope.get("headers") or ():
        if key == b"content-length":
            try:
                return int(value)
            except ValueError:
                return None
    return None
