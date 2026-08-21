from fastapi import APIRouter, Depends

from ..auth import get_store, now
from ..errors import ApiError
from ..models import GuestLink, InterviewSession, JoinPreview, JoinRequest, JoinResponse, SessionState
from ..store import Store

router = APIRouter(prefix="/v1/join", tags=["join"])


def _validate(link: GuestLink | None, session: InterviewSession | None, store: Store) -> str | None:
    """Returns a rejection reason, or None if the link is currently usable."""
    if link is None or session is None:
        return "This link is not valid."
    if link.revoked_at is not None:
        return "This link was revoked."
    if link.expires_at is not None and link.expires_at < now():
        return "This link has expired."
    if session.state == SessionState.archived:
        return "This interview is archived."
    if link.max_uses is not None and store.guest_link_uses.get(link.id, 0) >= link.max_uses:
        return "This link has reached its participant limit."
    return None


@router.get("/{token}", response_model=JoinPreview)
async def preview_join(token: str, store: Store = Depends(get_store)) -> JoinPreview:
    link = store.find_guest_link_by_token(token)
    session = store.sessions.get(link.session_id) if link else None
    reason = _validate(link, session, store)
    if reason is not None:
        return JoinPreview(session_title=session.title if session else "", joinable=False, reason=reason)
    return JoinPreview(session_title=session.title, joinable=True)


@router.post("/{token}", response_model=JoinResponse, status_code=201)
async def join(token: str, body: JoinRequest, store: Store = Depends(get_store)) -> JoinResponse:
    link = store.find_guest_link_by_token(token)
    session = store.sessions.get(link.session_id) if link else None
    reason = _validate(link, session, store)
    if reason is not None:
        status_code = 404 if link is None or session is None else 409
        raise ApiError(status_code, "not_joinable", reason)

    participant, updated_session = store.add_guest_participant(session, link, body.display_name)
    collaboration_token = store.issue_participant_token(session.id, participant.id)
    return JoinResponse(session=updated_session, participant=participant, collaboration_token=collaboration_token)
