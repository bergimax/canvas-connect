from fastapi import APIRouter, Depends

from ..auth import TokenRecord, get_current_actor, get_store
from ..errors import ApiError
from ..models import CreateSessionRequest, InterviewSession, Role, SessionState, UpdateSessionRequest
from ..store import Store

router = APIRouter(prefix="/v1/sessions", tags=["sessions"])


@router.post("", response_model=InterviewSession, status_code=201)
async def create_session(
    body: CreateSessionRequest,
    actor: TokenRecord = Depends(get_current_actor),
    store: Store = Depends(get_store),
) -> InterviewSession:
    if actor.subject != "user":
        raise ApiError(403, "forbidden", "Only interviewers can create sessions")
    owner = store.users[actor.user_id]
    return store.create_session(owner=owner, title=body.title, prompt=body.prompt or "", scheduled_at=body.scheduled_at)


@router.get("", response_model=list[InterviewSession])
async def list_sessions(
    actor: TokenRecord = Depends(get_current_actor),
    store: Store = Depends(get_store),
) -> list[InterviewSession]:
    return store.list_sessions_for_actor(actor)


@router.get("/{id}", response_model=InterviewSession)
async def get_session(
    id: str,
    actor: TokenRecord = Depends(get_current_actor),
    store: Store = Depends(get_store),
) -> InterviewSession:
    session = store.get_session_or_404(id)
    store.require_participant(session, actor)
    return session


@router.patch("/{id}", response_model=InterviewSession)
async def update_session(
    id: str,
    body: UpdateSessionRequest,
    actor: TokenRecord = Depends(get_current_actor),
    store: Store = Depends(get_store),
) -> InterviewSession:
    session = store.get_session_or_404(id)
    store.require_role(session, actor, {Role.owner, Role.interviewer})
    return store.update_session(session, body.model_dump(exclude_unset=True))


@router.post("/{id}/start", response_model=InterviewSession)
async def start_session(
    id: str,
    actor: TokenRecord = Depends(get_current_actor),
    store: Store = Depends(get_store),
) -> InterviewSession:
    session = store.get_session_or_404(id)
    store.require_role(session, actor, {Role.owner})
    if session.state in (SessionState.ended, SessionState.archived):
        raise ApiError(409, "invalid_state", f"Cannot start a session in state '{session.state.value}'")
    return store.start_session(session)


@router.post("/{id}/end", response_model=InterviewSession)
async def end_session(
    id: str,
    actor: TokenRecord = Depends(get_current_actor),
    store: Store = Depends(get_store),
) -> InterviewSession:
    session = store.get_session_or_404(id)
    store.require_role(session, actor, {Role.owner})
    if session.state != SessionState.live:
        raise ApiError(409, "invalid_state", f"Cannot end a session in state '{session.state.value}'")
    return store.end_session(session)


@router.post("/{id}/duplicate", response_model=InterviewSession, status_code=201)
async def duplicate_session(
    id: str,
    actor: TokenRecord = Depends(get_current_actor),
    store: Store = Depends(get_store),
) -> InterviewSession:
    session = store.get_session_or_404(id)
    store.require_role(session, actor, {Role.owner})
    return store.duplicate_session(session)


@router.post("/{id}/archive", response_model=InterviewSession)
async def archive_session(
    id: str,
    actor: TokenRecord = Depends(get_current_actor),
    store: Store = Depends(get_store),
) -> InterviewSession:
    session = store.get_session_or_404(id)
    store.require_role(session, actor, {Role.owner})
    return store.archive_session(session)
