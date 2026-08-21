"""In-memory data store, seeded with demo data.

Not thread-safe beyond what a single-process asyncio event loop already
guarantees between `await` points; fine for a demo/dev backend.
"""

from __future__ import annotations

import hashlib
import secrets

from .auth import TOKEN_TTL, TokenRecord, hash_password, new_token, now
from .errors import ApiError
from .models import (
    BoxElement,
    ConnectorElement,
    ConnectorEndpoint,
    CanvasDocument,
    GuestLink,
    InterviewSession,
    Participant,
    ConnectionState,
    Role,
    SessionState,
    StrokeElement,
    User,
)

PARTICIPANT_COLORS = [
    "#f97316",
    "#6366f1",
    "#22c55e",
    "#ec4899",
    "#06b6d4",
    "#eab308",
    "#8b5cf6",
    "#ef4444",
]


def _id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(6)}"


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class Store:
    def __init__(self) -> None:
        self.users: dict[str, User] = {}
        self.passwords: dict[str, str] = {}  # user_id -> hashed password
        self.users_by_email: dict[str, str] = {}  # lowercased email -> user_id
        self.sessions: dict[str, InterviewSession] = {}
        self.guest_links: dict[str, GuestLink] = {}
        self.guest_link_hash_index: dict[str, str] = {}  # sha256(token) -> link_id
        self.guest_link_uses: dict[str, int] = {}
        self.canvases: dict[str, CanvasDocument] = {}
        self.tokens: dict[str, TokenRecord] = {}
        self._seed()

    # ------------------------------ users ------------------------------

    def create_user(self, email: str, display_name: str, password: str, organization_id: str | None = None) -> User:
        user_id = _id("usr")
        user = User(id=user_id, email=email, display_name=display_name, organization_id=organization_id, created_at=now())
        self.users[user_id] = user
        self.passwords[user_id] = hash_password(password)
        self.users_by_email[email.lower()] = user_id
        return user

    def find_user_by_email(self, email: str) -> User | None:
        user_id = self.users_by_email.get(email.lower())
        return self.users.get(user_id) if user_id else None

    def issue_user_token(self, user_id: str) -> str:
        token = new_token()
        self.tokens[token] = TokenRecord(
            subject="user", user_id=user_id, participant_id=None, session_id=None, expires_at=now() + TOKEN_TTL
        )
        return token

    def issue_participant_token(self, session_id: str, participant_id: str) -> str:
        token = new_token()
        self.tokens[token] = TokenRecord(
            subject="participant",
            user_id=None,
            participant_id=participant_id,
            session_id=session_id,
            expires_at=now() + TOKEN_TTL,
        )
        return token

    # ---------------------------- sessions -----------------------------

    def get_session_or_404(self, session_id: str) -> InterviewSession:
        session = self.sessions.get(session_id)
        if session is None:
            raise ApiError(404, "not_found", "Session not found")
        return session

    def list_sessions_for_actor(self, actor: TokenRecord) -> list[InterviewSession]:
        result = []
        for session in self.sessions.values():
            if session.state == SessionState.archived:
                continue
            if actor.subject == "user":
                if session.owner_user_id == actor.user_id or any(p.user_id == actor.user_id for p in session.participants):
                    result.append(session)
            else:
                if any(p.id == actor.participant_id for p in session.participants):
                    result.append(session)
        result.sort(key=lambda s: s.created_at, reverse=True)
        return result

    def create_session(
        self,
        owner: User,
        title: str,
        prompt: str,
        scheduled_at,
    ) -> InterviewSession:
        session_id = _id("ses")
        owner_participant = Participant(
            id=_id("prt"),
            session_id=session_id,
            user_id=owner.id,
            display_name=owner.display_name,
            role=Role.owner,
            color=PARTICIPANT_COLORS[0],
            joined_at=now(),
            left_at=None,
            connection_state=ConnectionState.connected,
        )
        session = InterviewSession(
            id=session_id,
            owner_user_id=owner.id,
            title=title,
            prompt=prompt,
            state=SessionState.draft,
            candidate_editing_enabled=True,
            cursors_visible=True,
            scheduled_at=scheduled_at,
            started_at=None,
            ended_at=None,
            created_at=now(),
            updated_at=now(),
            participants=[owner_participant],
        )
        self.sessions[session_id] = session
        self.canvases[session_id] = CanvasDocument(
            id=_id("doc"), session_id=session_id, schema_version=1, latest_operation_cursor=0, updated_at=now(), elements=[]
        )
        return session

    def update_session(self, session: InterviewSession, patch: dict) -> InterviewSession:
        updated = session.model_copy(update={**patch, "updated_at": now()})
        self.sessions[session.id] = updated
        return updated

    def start_session(self, session: InterviewSession) -> InterviewSession:
        updated = session.model_copy(
            update={"state": SessionState.live, "started_at": session.started_at or now(), "updated_at": now()}
        )
        self.sessions[session.id] = updated
        return updated

    def end_session(self, session: InterviewSession) -> InterviewSession:
        updated = session.model_copy(
            update={
                "state": SessionState.ended,
                "ended_at": now(),
                "candidate_editing_enabled": False,
                "updated_at": now(),
            }
        )
        self.sessions[session.id] = updated
        return updated

    def archive_session(self, session: InterviewSession) -> InterviewSession:
        updated = session.model_copy(update={"state": SessionState.archived, "updated_at": now()})
        self.sessions[session.id] = updated
        return updated

    def duplicate_session(self, session: InterviewSession) -> InterviewSession:
        new_id = _id("ses")
        owner_participant = next(p for p in session.participants if p.role == Role.owner)
        copied_owner = owner_participant.model_copy(
            update={"id": _id("prt"), "session_id": new_id, "joined_at": now(), "left_at": None}
        )
        new_session = InterviewSession(
            id=new_id,
            owner_user_id=session.owner_user_id,
            title=f"{session.title} (copy)",
            prompt=session.prompt,
            state=SessionState.draft,
            candidate_editing_enabled=True,
            cursors_visible=session.cursors_visible,
            scheduled_at=None,
            started_at=None,
            ended_at=None,
            created_at=now(),
            updated_at=now(),
            participants=[copied_owner],
        )
        self.sessions[new_id] = new_session
        src_doc = self.canvases.get(session.id)
        self.canvases[new_id] = CanvasDocument(
            id=_id("doc"),
            session_id=new_id,
            schema_version=1,
            latest_operation_cursor=0,
            updated_at=now(),
            elements=[e.model_copy(deep=True) for e in src_doc.elements] if src_doc else [],
        )
        return new_session

    def remove_participant(self, session: InterviewSession, participant_id: str) -> None:
        if not any(p.id == participant_id for p in session.participants):
            raise ApiError(404, "not_found", "Participant not found")
        updated = session.model_copy(
            update={
                "participants": [p for p in session.participants if p.id != participant_id],
                "updated_at": now(),
            }
        )
        self.sessions[session.id] = updated

    # ------------------------- permission checks -------------------------

    def resolve_participant(self, session: InterviewSession, actor: TokenRecord) -> Participant | None:
        if actor.subject == "participant":
            if actor.session_id != session.id:
                return None
            return next((p for p in session.participants if p.id == actor.participant_id), None)
        return next((p for p in session.participants if p.user_id == actor.user_id), None)

    def require_participant(self, session: InterviewSession, actor: TokenRecord) -> Participant:
        participant = self.resolve_participant(session, actor)
        if participant is None:
            raise ApiError(403, "forbidden", "Not a participant of this session")
        return participant

    def require_role(self, session: InterviewSession, actor: TokenRecord, allowed: set[Role]) -> Participant:
        participant = self.require_participant(session, actor)
        if participant.role not in allowed:
            raise ApiError(403, "forbidden", "Insufficient permissions for this action")
        return participant

    # --------------------------- guest links ---------------------------

    def create_guest_link(
        self,
        session: InterviewSession,
        role_granted: Role,
        expires_at,
        max_uses: int | None,
        base_url: str,
    ) -> GuestLink:
        # Rotation semantics: a new link revokes any previously active link.
        for link in list(self.guest_links.values()):
            if link.session_id == session.id and link.revoked_at is None:
                self.guest_links[link.id] = link.model_copy(update={"revoked_at": now()})

        raw_token = new_token()
        link_id = _id("lnk")
        url = f"{base_url.rstrip('/')}/join/{raw_token}"
        link = GuestLink(
            id=link_id,
            session_id=session.id,
            url=url,
            role_granted=role_granted,
            expires_at=expires_at,
            max_uses=max_uses,
            revoked_at=None,
            created_at=now(),
        )
        self.guest_links[link_id] = link
        self.guest_link_hash_index[_hash_token(raw_token)] = link_id
        self.guest_link_uses[link_id] = 0
        return link

    def list_guest_links(self, session: InterviewSession) -> list[GuestLink]:
        return [
            link
            for link in self.guest_links.values()
            if link.session_id == session.id and link.revoked_at is None
        ]

    def revoke_guest_link(self, session: InterviewSession, link_id: str) -> None:
        link = self.guest_links.get(link_id)
        if link is None or link.session_id != session.id:
            raise ApiError(404, "not_found", "Guest link not found")
        self.guest_links[link_id] = link.model_copy(update={"revoked_at": now()})

    def find_guest_link_by_token(self, token: str) -> GuestLink | None:
        link_id = self.guest_link_hash_index.get(_hash_token(token))
        return self.guest_links.get(link_id) if link_id else None

    def add_guest_participant(
        self, session: InterviewSession, link: GuestLink, display_name: str
    ) -> tuple[Participant, InterviewSession]:
        participant = Participant(
            id=_id("prt"),
            session_id=session.id,
            user_id=None,
            display_name=display_name,
            role=link.role_granted,
            color=PARTICIPANT_COLORS[len(session.participants) % len(PARTICIPANT_COLORS)],
            joined_at=now(),
            left_at=None,
            connection_state=ConnectionState.connected,
        )
        new_state = session.state
        started_at = session.started_at
        if session.state == SessionState.draft:
            new_state = SessionState.live
            started_at = started_at or now()
        updated_session = session.model_copy(
            update={
                "participants": [*session.participants, participant],
                "state": new_state,
                "started_at": started_at,
                "updated_at": now(),
            }
        )
        self.sessions[session.id] = updated_session
        self.guest_link_uses[link.id] = self.guest_link_uses.get(link.id, 0) + 1
        return participant, updated_session

    # ------------------------------ canvas ------------------------------

    def get_or_create_canvas(self, session: InterviewSession) -> CanvasDocument:
        doc = self.canvases.get(session.id)
        if doc is None:
            doc = CanvasDocument(
                id=_id("doc"),
                session_id=session.id,
                schema_version=1,
                latest_operation_cursor=0,
                updated_at=now(),
                elements=[],
            )
            self.canvases[session.id] = doc
        return doc

    def save_canvas(self, session: InterviewSession, document: CanvasDocument) -> CanvasDocument:
        updated = document.model_copy(update={"session_id": session.id, "updated_at": now()})
        self.canvases[session.id] = updated
        self.sessions[session.id] = session.model_copy(update={"updated_at": now()})
        return updated

    # ------------------------------- seed -------------------------------

    def _seed(self) -> None:
        owner = self.create_user(
            email="interviewer@example.com",
            display_name="Alex Moreau",
            password="password123",
            organization_id="org_demo",
        )

        live_session = self.create_session(
            owner=owner,
            title="Design a URL shortener",
            prompt=(
                "Design a highly available URL shortening service handling 10k writes/s "
                "and 500k reads/s. Discuss data model, caching, and failure modes."
            ),
            scheduled_at=None,
        )
        live_session = self.start_session(live_session)
        candidate = Participant(
            id=_id("prt"),
            session_id=live_session.id,
            user_id=None,
            display_name="Jordan Lee",
            role=Role.candidate,
            color=PARTICIPANT_COLORS[1],
            joined_at=now(),
            left_at=None,
            connection_state=ConnectionState.connected,
        )
        live_session = live_session.model_copy(update={"participants": [*live_session.participants, candidate]})
        self.sessions[live_session.id] = live_session
        self.canvases[live_session.id] = _seed_canvas(live_session.id, owner.id)

        draft_session = self.create_session(
            owner=owner,
            title="Design a rate limiter",
            prompt="Design a distributed rate limiter for a public API gateway.",
            scheduled_at=None,
        )
        self.sessions[draft_session.id] = draft_session

        ended_session = self.create_session(
            owner=owner,
            title="Design a chat application",
            prompt="Design the backend for a WhatsApp-like real-time chat application.",
            scheduled_at=None,
        )
        ended_session = self.start_session(ended_session)
        ended_session = self.end_session(ended_session)
        self.sessions[ended_session.id] = ended_session


def _seed_canvas(session_id: str, actor_id: str) -> CanvasDocument:
    ts = now()

    def box(id_, x, y, w, h, label, component_type):
        return BoxElement(
            id=id_,
            kind="component",
            x=x,
            y=y,
            z=0,
            parent_id=None,
            created_by=actor_id,
            created_at=ts,
            updated_at=ts,
            width=w,
            height=h,
            label=label,
            componentType=component_type,
        )

    def connector(id_, from_id, to_id, from_xy, to_xy):
        return ConnectorElement(
            id=id_,
            kind="connector",
            x=0,
            y=0,
            z=0,
            parent_id=None,
            created_by=actor_id,
            created_at=ts,
            updated_at=ts,
            **{"from": ConnectorEndpoint(elementId=from_id, x=from_xy[0], y=from_xy[1])},
            to=ConnectorEndpoint(elementId=to_id, x=to_xy[0], y=to_xy[1]),
            style="elbow",
            dashed=False,
            color="#64748b",
            strokeWidth=2,
            arrowStart=False,
            arrowEnd=True,
        )

    client = box("el_client", 40, 200, 140, 70, "Client", "client")
    gateway = box("el_gateway", 260, 200, 160, 70, "API Gateway", "api-gateway")
    service = box("el_service", 500, 200, 160, 70, "Shortener Service", "service")
    cache = box("el_cache", 740, 100, 140, 70, "Cache", "cache")
    db = box("el_db", 740, 300, 140, 70, "SQL DB", "sql-db")

    elements = [
        client,
        gateway,
        service,
        cache,
        db,
        connector("el_c1", client.id, gateway.id, (180, 235), (260, 235)),
        connector("el_c2", gateway.id, service.id, (420, 235), (500, 235)),
        connector("el_c3", service.id, cache.id, (660, 220), (740, 135)),
        connector("el_c4", service.id, db.id, (660, 250), (740, 335)),
    ]

    return CanvasDocument(
        id=_id("doc"),
        session_id=session_id,
        schema_version=1,
        latest_operation_cursor=len(elements),
        updated_at=ts,
        elements=elements,
    )
