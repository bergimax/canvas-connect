"""POST /v1/auth/magic-link, GET /v1/me, and the practical /v1/auth/login.

/v1/auth/magic-link and GET /v1/me are the endpoints documented in
/openapi.yaml. /v1/auth/login is an addition: the OpenAPI magic-link flow
can't deliver a real email in this demo environment, so login is the actual
path callers (including the test suite) use to exchange a password for a
bearer token.
"""

from fastapi import APIRouter, Depends

from ..auth import TokenRecord, get_current_actor, get_store, verify_password
from ..errors import ApiError
from ..models import LoginRequest, MagicLinkRequest, SentResponse, TokenResponse, User
from ..store import Store

router = APIRouter(tags=["auth"])


@router.post("/v1/auth/magic-link", response_model=SentResponse)
async def request_magic_link(_body: MagicLinkRequest) -> SentResponse:
    # No email provider is wired up in this demo backend. Always report
    # success (and never reveal whether the address is registered) — use
    # POST /v1/auth/login to actually obtain a token.
    return SentResponse(sent=True)


@router.post("/v1/auth/login", response_model=TokenResponse)
async def login(body: LoginRequest, store: Store = Depends(get_store)) -> TokenResponse:
    user = store.find_user_by_email(body.email)
    if user is None or not verify_password(body.password, store.get_password_hash(user.id)):
        raise ApiError(401, "invalid_credentials", "Email or password is incorrect")
    token = store.issue_user_token(user.id)
    return TokenResponse(access_token=token)


@router.get("/v1/me", response_model=User)
async def get_me(actor: TokenRecord = Depends(get_current_actor), store: Store = Depends(get_store)) -> User:
    if actor.subject != "user":
        raise ApiError(403, "forbidden", "Guests do not have a user profile")
    return store.get_user(actor.user_id)
