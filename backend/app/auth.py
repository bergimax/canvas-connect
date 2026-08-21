"""Password hashing and bearer-token authentication.

Two kinds of bearer token are issued:
  - "user" tokens, for interviewers who authenticated with email + password
    (see routers/auth.py — the OpenAPI-documented magic-link endpoint cannot
    deliver a real email in this environment, so /v1/auth/login is the
    practical path to a token; magic-link still returns {sent: true} as
    documented).
  - "participant" tokens, issued to guests on POST /v1/join/{token} and
    reissued by GET /v1/sessions/{id}/canvas as the collaboration credential.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal

import bcrypt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .errors import ApiError

TOKEN_TTL = timedelta(hours=12)


def now() -> datetime:
    return datetime.now(timezone.utc)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def new_token() -> str:
    return secrets.token_urlsafe(32)


@dataclass(frozen=True)
class TokenRecord:
    subject: Literal["user", "participant"]
    user_id: str | None
    participant_id: str | None
    session_id: str | None
    expires_at: datetime


def get_store(request: Request):
    # Imported lazily to avoid a circular import (store imports auth for token issuance).
    return request.app.state.store


_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_actor(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    store=Depends(get_store),
) -> TokenRecord:
    if credentials is None:
        raise ApiError(401, "unauthenticated", "Missing bearer token")
    record = store.get_token(credentials.credentials)
    if record is None or record.expires_at < now():
        raise ApiError(401, "unauthenticated", "Invalid or expired token")
    return record
