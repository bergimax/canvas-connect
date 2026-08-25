"""Liveness/readiness probe, used by the Docker healthcheck and by CI/CD
after a deploy to confirm the app actually came up (not just that some
process is listening on the port).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy import text

from ..auth import get_store
from ..store import Store

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(response: Response, store: Store = Depends(get_store)) -> dict:
    try:
        store.session.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - any DB failure means "not healthy"
        response.status_code = 503
        return {"status": "error", "detail": str(exc)}
    return {"status": "ok"}
