"""SQLAlchemy-backed data store, seeded with demo data on first run.

`Store` is the API boundary between routers and storage: routers only ever
call its methods and never touch SQLAlchemy directly. A single `Store`
(wrapping a single `Session`) lives for the app's lifetime on
`app.state.store` — safe because every route handler is `async def` with no
`await` around Store calls, so they all run on the single event-loop
thread, never handed off to a worker thread.
"""

from __future__ import annotations

import hashlib
import secrets
from enum import Enum

from sqlalchemy import func
from sqlalchemy.orm import Session

from .auth import TOKEN_TTL, TokenRecord, hash_password, new_token, now
from .db import CanvasDocumentRow, GuestLinkRow, ParticipantRow, SessionRow, TokenRow, UserRow
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


def _value(x):
    """Enum -> its stored string value; anything else passed through."""
    return x.value if isinstance(x, Enum) else x


# --------------------------- ORM row -> Pydantic model ---------------------------


def _user_model(row: UserRow) -> User:
    return User(
        id=row.id,
        email=row.email,
        display_name=row.display_name,
        organization_id=row.organization_id,
        created_at=row.created_at,
    )


def _participant_model(row: ParticipantRow) -> Participant:
    return Participant(
        id=row.id,
        session_id=row.session_id,
        user_id=row.user_id,
        display_name=row.display_name,
        role=row.role,
        color=row.color,
        joined_at=row.joined_at,
        left_at=row.left_at,
        connection_state=row.connection_state,
        cursor=row.cursor,
        selection=row.selection or [],
    )


def _session_model(row: SessionRow) -> InterviewSession:
    return InterviewSession(
        id=row.id,
        owner_user_id=row.owner_user_id,
        title=row.title,
        prompt=row.prompt,
        state=row.state,
        candidate_editing_enabled=row.candidate_editing_enabled,
        cursors_visible=row.cursors_visible,
        scheduled_at=row.scheduled_at,
        started_at=row.started_at,
        ended_at=row.ended_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
        participants=[_participant_model(p) for p in row.participants],
    )


def _guest_link_model(row: GuestLinkRow) -> GuestLink:
    return GuestLink(
        id=row.id,
        session_id=row.session_id,
        url=row.url,
        role_granted=row.role_granted,
        expires_at=row.expires_at,
        max_uses=row.max_uses,
        revoked_at=row.revoked_at,
        created_at=row.created_at,
    )


def _canvas_model(row: CanvasDocumentRow) -> CanvasDocument:
    return CanvasDocument(
        id=row.id,
        session_id=row.session_id,
        schema_version=row.schema_version,
        latest_operation_cursor=row.latest_operation_cursor,
        updated_at=row.updated_at,
        elements=row.elements or [],
    )


def _elements_json(document: CanvasDocument) -> list[dict]:
    # mode="json" turns datetimes etc. into JSON-safe primitives so the
    # generic JSON column can serialize them on any backend.
    return [e.model_dump(mode="json", by_alias=True) for e in document.elements]


class Store:
    def __init__(self, session: Session) -> None:
        self.session = session
        if self.session.query(UserRow).count() == 0:
            self._seed()

    # ------------------------------ users ------------------------------

    def create_user(
        self, email: str, display_name: str, password: str, organization_id: str | None = None
    ) -> User:
        row = UserRow(
            id=_id("usr"),
            email=email,
            display_name=display_name,
            organization_id=organization_id,
            password_hash=hash_password(password),
            created_at=now(),
        )
        self.session.add(row)
        self.session.commit()
        return _user_model(row)

    def find_user_by_email(self, email: str) -> User | None:
        row = self.session.query(UserRow).filter(func.lower(UserRow.email) == email.lower()).first()
        return _user_model(row) if row else None

    def get_user(self, user_id: str) -> User:
        row = self.session.get(UserRow, user_id)
        if row is None:
            raise ApiError(404, "not_found", "User not found")
        return _user_model(row)

    def get_password_hash(self, user_id: str) -> str:
        row = self.session.get(UserRow, user_id)
        if row is None:
            raise ApiError(404, "not_found", "User not found")
        return row.password_hash

    def issue_user_token(self, user_id: str) -> str:
        token = new_token()
        self.session.add(
            TokenRow(
                token=token, subject="user", user_id=user_id, participant_id=None, session_id=None,
                expires_at=now() + TOKEN_TTL,
            )
        )
        self.session.commit()
        return token

    def issue_participant_token(self, session_id: str, participant_id: str) -> str:
        token = new_token()
        self.session.add(
            TokenRow(
                token=token, subject="participant", user_id=None, participant_id=participant_id,
                session_id=session_id, expires_at=now() + TOKEN_TTL,
            )
        )
        self.session.commit()
        return token

    def get_token(self, token: str) -> TokenRecord | None:
        row = self.session.get(TokenRow, token)
        if row is None:
            return None
        return TokenRecord(
            subject=row.subject,
            user_id=row.user_id,
            participant_id=row.participant_id,
            session_id=row.session_id,
            expires_at=row.expires_at,
        )

    # ---------------------------- sessions -----------------------------

    def get_session_or_404(self, session_id: str) -> InterviewSession:
        row = self.session.get(SessionRow, session_id)
        if row is None:
            raise ApiError(404, "not_found", "Session not found")
        return _session_model(row)

    def get_session(self, session_id: str) -> InterviewSession | None:
        row = self.session.get(SessionRow, session_id)
        return _session_model(row) if row else None

    def list_sessions_for_actor(self, actor: TokenRecord) -> list[InterviewSession]:
        rows = (
            self.session.query(SessionRow)
            .filter(SessionRow.state != SessionState.archived.value)
            .order_by(SessionRow.created_at.desc())
            .all()
        )
        result = []
        for row in rows:
            if actor.subject == "user":
                if row.owner_user_id == actor.user_id or any(p.user_id == actor.user_id for p in row.participants):
                    result.append(_session_model(row))
            else:
                if any(p.id == actor.participant_id for p in row.participants):
                    result.append(_session_model(row))
        return result

    def create_session(
        self,
        owner: User,
        title: str,
        prompt: str,
        scheduled_at,
    ) -> InterviewSession:
        session_id = _id("ses")
        ts = now()
        row = SessionRow(
            id=session_id,
            owner_user_id=owner.id,
            title=title,
            prompt=prompt,
            state=SessionState.draft.value,
            candidate_editing_enabled=True,
            cursors_visible=True,
            scheduled_at=scheduled_at,
            started_at=None,
            ended_at=None,
            created_at=ts,
            updated_at=ts,
        )
        row.participants.append(
            ParticipantRow(
                id=_id("prt"),
                session_id=session_id,
                user_id=owner.id,
                display_name=owner.display_name,
                role=Role.owner.value,
                color=PARTICIPANT_COLORS[0],
                joined_at=ts,
                left_at=None,
                connection_state=ConnectionState.connected.value,
                cursor=None,
                selection=[],
            )
        )
        self.session.add(row)
        # Flush so the sessions row exists before the canvas_documents insert
        # below — there's no relationship() between SessionRow and
        # CanvasDocumentRow, so the ORM doesn't otherwise order these two
        # inserts against each other, and a real FK-enforcing DB (Postgres,
        # unlike SQLite) rejects the insert if it lands first.
        self.session.flush()
        self.session.add(
            CanvasDocumentRow(
                id=_id("doc"), session_id=session_id, schema_version=1, latest_operation_cursor=0,
                updated_at=ts, elements=[],
            )
        )
        self.session.commit()
        return _session_model(row)

    def update_session(self, session: InterviewSession, patch: dict) -> InterviewSession:
        row = self.session.get(SessionRow, session.id)
        for key, value in patch.items():
            setattr(row, key, _value(value))
        row.updated_at = now()
        self.session.commit()
        return _session_model(row)

    def start_session(self, session: InterviewSession) -> InterviewSession:
        row = self.session.get(SessionRow, session.id)
        row.state = SessionState.live.value
        row.started_at = row.started_at or now()
        row.updated_at = now()
        self.session.commit()
        return _session_model(row)

    def end_session(self, session: InterviewSession) -> InterviewSession:
        row = self.session.get(SessionRow, session.id)
        row.state = SessionState.ended.value
        row.ended_at = now()
        row.candidate_editing_enabled = False
        row.updated_at = now()
        self.session.commit()
        return _session_model(row)

    def archive_session(self, session: InterviewSession) -> InterviewSession:
        row = self.session.get(SessionRow, session.id)
        row.state = SessionState.archived.value
        row.updated_at = now()
        self.session.commit()
        return _session_model(row)

    def duplicate_session(self, session: InterviewSession) -> InterviewSession:
        new_id = _id("ses")
        ts = now()
        owner_participant = next(p for p in session.participants if p.role == Role.owner)
        new_row = SessionRow(
            id=new_id,
            owner_user_id=session.owner_user_id,
            title=f"{session.title} (copy)",
            prompt=session.prompt,
            state=SessionState.draft.value,
            candidate_editing_enabled=True,
            cursors_visible=session.cursors_visible,
            scheduled_at=None,
            started_at=None,
            ended_at=None,
            created_at=ts,
            updated_at=ts,
        )
        new_row.participants.append(
            ParticipantRow(
                id=_id("prt"),
                session_id=new_id,
                user_id=owner_participant.user_id,
                display_name=owner_participant.display_name,
                role=owner_participant.role.value,
                color=owner_participant.color,
                joined_at=ts,
                left_at=None,
                connection_state=(
                    owner_participant.connection_state.value if owner_participant.connection_state else None
                ),
                cursor=None,
                selection=[],
            )
        )
        self.session.add(new_row)
        # See create_session: flush before inserting the dependent
        # canvas_documents row so a FK-enforcing DB doesn't reject it.
        self.session.flush()
        src_doc = self._get_canvas_row(session.id)
        self.session.add(
            CanvasDocumentRow(
                id=_id("doc"),
                session_id=new_id,
                schema_version=1,
                latest_operation_cursor=0,
                updated_at=ts,
                elements=list(src_doc.elements) if src_doc else [],
            )
        )
        self.session.commit()
        return _session_model(new_row)

    def remove_participant(self, session: InterviewSession, participant_id: str) -> None:
        row = self.session.get(ParticipantRow, participant_id)
        if row is None or row.session_id != session.id:
            raise ApiError(404, "not_found", "Participant not found")
        self.session.delete(row)
        session_row = self.session.get(SessionRow, session.id)
        session_row.updated_at = now()
        self.session.commit()

    # ------------------------- permission checks -------------------------
    # Pure functions over the already-loaded Pydantic model — no DB access.

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
        active = self.session.query(GuestLinkRow).filter_by(session_id=session.id, revoked_at=None).all()
        for link_row in active:
            link_row.revoked_at = now()

        raw_token = new_token()
        url = f"{base_url.rstrip('/')}/join/{raw_token}"
        row = GuestLinkRow(
            id=_id("lnk"),
            session_id=session.id,
            url=url,
            token_hash=_hash_token(raw_token),
            role_granted=role_granted.value,
            expires_at=expires_at,
            max_uses=max_uses,
            use_count=0,
            revoked_at=None,
            created_at=now(),
        )
        self.session.add(row)
        self.session.commit()
        return _guest_link_model(row)

    def list_guest_links(self, session: InterviewSession) -> list[GuestLink]:
        rows = self.session.query(GuestLinkRow).filter_by(session_id=session.id, revoked_at=None).all()
        return [_guest_link_model(r) for r in rows]

    def revoke_guest_link(self, session: InterviewSession, link_id: str) -> None:
        row = self.session.get(GuestLinkRow, link_id)
        if row is None or row.session_id != session.id:
            raise ApiError(404, "not_found", "Guest link not found")
        row.revoked_at = now()
        self.session.commit()

    def find_guest_link_by_token(self, token: str) -> GuestLink | None:
        row = self.session.query(GuestLinkRow).filter_by(token_hash=_hash_token(token)).first()
        return _guest_link_model(row) if row else None

    def get_guest_link_use_count(self, link_id: str) -> int:
        row = self.session.get(GuestLinkRow, link_id)
        return row.use_count if row else 0

    def add_guest_participant(
        self, session: InterviewSession, link: GuestLink, display_name: str
    ) -> tuple[Participant, InterviewSession]:
        session_row = self.session.get(SessionRow, session.id)
        participant_row = ParticipantRow(
            id=_id("prt"),
            session_id=session.id,
            user_id=None,
            display_name=display_name,
            role=link.role_granted.value,
            color=PARTICIPANT_COLORS[len(session.participants) % len(PARTICIPANT_COLORS)],
            joined_at=now(),
            left_at=None,
            connection_state=ConnectionState.connected.value,
            cursor=None,
            selection=[],
        )
        session_row.participants.append(participant_row)
        if session_row.state == SessionState.draft.value:
            session_row.state = SessionState.live.value
            session_row.started_at = session_row.started_at or now()
        session_row.updated_at = now()

        link_row = self.session.get(GuestLinkRow, link.id)
        link_row.use_count += 1

        self.session.commit()
        return _participant_model(participant_row), _session_model(session_row)

    # ------------------------------ canvas ------------------------------

    def _get_canvas_row(self, session_id: str) -> CanvasDocumentRow | None:
        return self.session.query(CanvasDocumentRow).filter_by(session_id=session_id).first()

    def get_or_create_canvas(self, session: InterviewSession) -> CanvasDocument:
        row = self._get_canvas_row(session.id)
        if row is None:
            row = CanvasDocumentRow(
                id=_id("doc"), session_id=session.id, schema_version=1, latest_operation_cursor=0,
                updated_at=now(), elements=[],
            )
            self.session.add(row)
            self.session.commit()
        return _canvas_model(row)

    def save_canvas(self, session: InterviewSession, document: CanvasDocument) -> CanvasDocument:
        row = self._get_canvas_row(session.id)
        ts = now()
        elements = _elements_json(document)
        if row is None:
            row = CanvasDocumentRow(
                id=document.id or _id("doc"), session_id=session.id, schema_version=document.schema_version,
                latest_operation_cursor=document.latest_operation_cursor, updated_at=ts, elements=elements,
            )
            self.session.add(row)
        else:
            row.schema_version = document.schema_version
            row.latest_operation_cursor = document.latest_operation_cursor
            row.elements = elements
            row.updated_at = ts
        session_row = self.session.get(SessionRow, session.id)
        session_row.updated_at = ts
        self.session.commit()
        return _canvas_model(row)

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
        session_row = self.session.get(SessionRow, live_session.id)
        session_row.participants.append(
            ParticipantRow(
                id=_id("prt"),
                session_id=live_session.id,
                user_id=None,
                display_name="Jordan Lee",
                role=Role.candidate.value,
                color=PARTICIPANT_COLORS[1],
                joined_at=now(),
                left_at=None,
                connection_state=ConnectionState.connected.value,
                cursor=None,
                selection=[],
            )
        )
        self.session.commit()

        seeded_canvas = _seed_canvas(live_session.id, owner.id)
        doc_row = self._get_canvas_row(live_session.id)
        doc_row.elements = _elements_json(seeded_canvas)
        doc_row.latest_operation_cursor = seeded_canvas.latest_operation_cursor
        doc_row.schema_version = seeded_canvas.schema_version
        doc_row.updated_at = seeded_canvas.updated_at
        self.session.commit()

        self.create_session(
            owner=owner,
            title="Design a rate limiter",
            prompt="Design a distributed rate limiter for a public API gateway.",
            scheduled_at=None,
        )

        ended_session = self.create_session(
            owner=owner,
            title="Design a chat application",
            prompt="Design the backend for a WhatsApp-like real-time chat application.",
            scheduled_at=None,
        )
        ended_session = self.start_session(ended_session)
        self.end_session(ended_session)


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
