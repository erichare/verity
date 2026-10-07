"""Bound bytes received before multipart or MCP JSON parsing, including chunked bodies."""

from __future__ import annotations

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from . import limits


class BodySizeLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        cap = limits.LIMITS.max_total_bytes
        rejection = JSONResponse(status_code=413, content={"detail": "request body too large"})
        for key, value in scope.get("headers", []):
            if key == b"content-length":
                try:
                    if int(value) > cap:
                        await rejection(scope, receive, send)
                        return
                except ValueError:
                    pass
        received = 0
        exceeded = False
        started = False
        rejected = False

        async def limited_receive() -> Message:
            nonlocal received, exceeded
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > cap:
                    exceeded = True
                    raise limits.UploadTooLarge("request body too large")
            return message

        async def limited_send(message: Message) -> None:
            nonlocal started, rejected
            # Multipart and MCP parsers may catch the read exception and turn it
            # into a generic 400. Preserve the public 413 contract in that case.
            if exceeded and not started:
                if not rejected:
                    await rejection(scope, receive, send)
                    rejected = True
                return
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, limited_send)
        except Exception:
            if not exceeded or started:
                raise
            if not rejected:
                await rejection(scope, receive, send)
