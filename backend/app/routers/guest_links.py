from fastapi import APIRouter, Depends, Request

from ..auth import TokenRecord, get_current_actor, get_store
from ..models import CreateGuestLinkRequest, GuestLink, Role
from ..store import Store

router = APIRouter(prefix="/v1/sessions/{id}/guest-links", tags=["guest-links"])


@router.post("", response_model=GuestLink, status_code=201)
async def create_guest_link(
    id: str,
    body: CreateGuestLinkRequest,
    request: Request,
    actor: TokenRecord = Depends(get_current_actor),
    store: Store = Depends(get_store),
) -> GuestLink:
    session = store.get_session_or_404(id)
    store.require_role(session, actor, {Role.owner, Role.interviewer})
    return store.create_guest_link(
        session,
        role_granted=body.role_granted or Role.candidate,
        expires_at=body.expires_at,
        max_uses=body.max_uses,
        base_url=str(request.base_url),
    )


@router.get("", response_model=list[GuestLink])
async def list_guest_links(
    id: str,
    actor: TokenRecord = Depends(get_current_actor),
    store: Store = Depends(get_store),
) -> list[GuestLink]:
    session = store.get_session_or_404(id)
    store.require_role(session, actor, {Role.owner, Role.interviewer})
    return store.list_guest_links(session)


@router.delete("/{link_id}", status_code=204)
async def revoke_guest_link(
    id: str,
    link_id: str,
    actor: TokenRecord = Depends(get_current_actor),
    store: Store = Depends(get_store),
) -> None:
    session = store.get_session_or_404(id)
    store.require_role(session, actor, {Role.owner})
    store.revoke_guest_link(session, link_id)
