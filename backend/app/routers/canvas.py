from fastapi import APIRouter, Depends

from ..auth import TokenRecord, get_current_actor, get_store
from ..errors import ApiError
from ..models import CanvasDocument, CanvasGetResponse, Role, SavedAtResponse
from ..store import Store
from ..telemetry import component_creation_failures, get_logger

router = APIRouter(prefix="/v1/sessions/{id}/canvas", tags=["canvas"])
logger = get_logger("canvas")


@router.get("", response_model=CanvasGetResponse)
async def get_canvas(
    id: str,
    actor: TokenRecord = Depends(get_current_actor),
    store: Store = Depends(get_store),
) -> CanvasGetResponse:
    session = store.get_session_or_404(id)
    participant = store.require_participant(session, actor)
    document = store.get_or_create_canvas(session)
    collaboration_token = store.issue_participant_token(session.id, participant.id)
    # No WebSocket collaboration gateway is implemented — see openapi.yaml's
    # note that the realtime protocol is documentation-only. The frontend's
    # RealtimeClient treats an empty websocket_url as "local mode".
    return CanvasGetResponse(document=document, collaboration_token=collaboration_token, websocket_url="")


@router.put("", response_model=SavedAtResponse)
async def save_canvas(
    id: str,
    body: CanvasDocument,
    actor: TokenRecord = Depends(get_current_actor),
    store: Store = Depends(get_store),
) -> SavedAtResponse:
    session = store.get_session_or_404(id)
    participant = store.require_participant(session, actor)
    if participant.role == Role.observer:
        component_creation_failures.add(1, {"reason": "observer_forbidden"})
        logger.warning(
            "Canvas save rejected: observer role",
            extra={"session_id": id, "participant_id": participant.id, "reason": "observer_forbidden"},
        )
        raise ApiError(403, "forbidden", "Observers cannot edit the canvas")
    if participant.role == Role.candidate and not session.candidate_editing_enabled:
        component_creation_failures.add(1, {"reason": "editing_disabled"})
        logger.warning(
            "Canvas save rejected: candidate editing disabled",
            extra={"session_id": id, "participant_id": participant.id, "reason": "editing_disabled"},
        )
        raise ApiError(403, "forbidden", "Candidate editing is disabled for this session")
    try:
        saved = store.save_canvas(session, body)
    except Exception:
        component_creation_failures.add(1, {"reason": "error"})
        logger.exception("Canvas save failed", extra={"session_id": id, "participant_id": participant.id})
        raise
    return SavedAtResponse(saved_at=saved.updated_at)
