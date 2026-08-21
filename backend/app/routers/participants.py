from fastapi import APIRouter, Depends

from ..auth import TokenRecord, get_current_actor, get_store
from ..models import Role
from ..store import Store

router = APIRouter(prefix="/v1/sessions/{id}/participants", tags=["participants"])


@router.delete("/{participant_id}", status_code=204)
async def remove_participant(
    id: str,
    participant_id: str,
    actor: TokenRecord = Depends(get_current_actor),
    store: Store = Depends(get_store),
) -> None:
    session = store.get_session_or_404(id)
    store.require_role(session, actor, {Role.owner})
    store.remove_participant(session, participant_id)
