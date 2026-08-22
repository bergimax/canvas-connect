"""Reverse-proxies every non-API request to the built frontend server.

In the Docker image, `docker-entrypoint.sh` starts the frontend's own Node
server (built by nitro's node-server preset) as an internal-only process and
this backend is the sole exposed port — the browser only ever talks to
FastAPI. All `/v1/*` routes are handled by this app directly; everything
else (the app shell, hashed JS/CSS assets, favicon, etc.) is forwarded here.
"""

from __future__ import annotations

import os

import httpx
from fastapi import FastAPI, Request, Response

# Headers that are specific to the hop between this proxy and the upstream
# (or vice versa) and must not be copied across it verbatim.
_HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "content-encoding",
    "content-length",
    "host",
    "date",
    "server",
}


def register_frontend_proxy(app: FastAPI) -> None:
    frontend_origin = os.environ.get("FRONTEND_ORIGIN", "http://127.0.0.1:3000")
    client = httpx.AsyncClient(base_url=frontend_origin)

    @app.api_route("/{full_path:path}", methods=["GET", "HEAD"])
    async def proxy_to_frontend(full_path: str, request: Request) -> Response:
        upstream_request = client.build_request(
            request.method,
            f"/{full_path}",
            params=request.query_params,
            headers=[(k, v) for k, v in request.headers.items() if k.lower() not in _HOP_BY_HOP_HEADERS],
        )
        try:
            upstream_response = await client.send(upstream_request)
        except httpx.ConnectError:
            return Response("Frontend is unavailable.", status_code=502)

        headers = {
            k: v for k, v in upstream_response.headers.items() if k.lower() not in _HOP_BY_HOP_HEADERS
        }
        return Response(
            content=upstream_response.content,
            status_code=upstream_response.status_code,
            headers=headers,
        )
