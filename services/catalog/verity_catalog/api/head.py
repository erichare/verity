"""HEAD-for-GET: answer ``HEAD`` on every ``GET`` route.

FastAPI/Starlette only route ``HEAD`` where a route declares it, so uptime
monitors and link checkers probing downloads (e.g. the benchmark kits) with
``HEAD`` got 405 "Method Not Allowed". This pure-ASGI middleware rewrites an
incoming ``HEAD`` to ``GET`` for the inner app and strips the response body
while preserving every header (``Content-Length``, ``ETag``,
``Content-Type``…) — exactly the RFC 9110 HEAD contract.
"""

from __future__ import annotations

from starlette.types import ASGIApp, Message, Receive, Scope, Send


class HeadRequestMiddleware:
    """Serve ``HEAD`` requests from the matching ``GET`` route, body stripped."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method") != "HEAD":
            await self.app(scope, receive, send)
            return

        async def send_without_body(message: Message) -> None:
            if message["type"] == "http.response.body":
                # Keep the framing (more_body) but drop the payload; the
                # headers already sent carry the true Content-Length.
                message = {
                    "type": "http.response.body",
                    "body": b"",
                    "more_body": message.get("more_body", False),
                }
            await send(message)

        # New scope dict (the original is not mutated) so routing sees GET.
        await self.app({**scope, "method": "GET"}, receive, send_without_body)
