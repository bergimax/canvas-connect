"""Pydantic schemas mirroring the components in /openapi.yaml."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal, Union

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class Role(str, Enum):
    owner = "owner"
    interviewer = "interviewer"
    candidate = "candidate"
    observer = "observer"


class SessionState(str, Enum):
    draft = "draft"
    live = "live"
    ended = "ended"
    archived = "archived"


class ConnectionState(str, Enum):
    connected = "connected"
    reconnecting = "reconnecting"
    offline = "offline"


class ComponentType(str, Enum):
    service = "service"
    rounded = "rounded"
    boundary = "boundary"
    generic = "generic"
    sql_db = "sql-db"
    nosql_db = "nosql-db"
    cache = "cache"
    object_storage = "object-storage"
    warehouse = "warehouse"
    queue = "queue"
    stream = "stream"
    pubsub = "pubsub"
    client = "client"
    mobile_client = "mobile-client"
    api_gateway = "api-gateway"
    load_balancer = "load-balancer"
    cdn = "cdn"
    external_api = "external-api"
    server = "server"
    worker = "worker"
    function = "function"
    container = "container"
    llm = "llm"
    embedding = "embedding"
    vector_db = "vector-db"
    agent = "agent"


class Error(BaseModel):
    code: str
    message: str


class User(BaseModel):
    id: str
    email: EmailStr
    display_name: str
    organization_id: str | None = None
    created_at: datetime


class Cursor(BaseModel):
    x: float
    y: float


class Participant(BaseModel):
    id: str
    session_id: str
    user_id: str | None = None
    display_name: str
    role: Role
    color: str
    joined_at: datetime
    left_at: datetime | None = None
    connection_state: ConnectionState | None = None
    cursor: Cursor | None = None
    selection: list[str] = Field(default_factory=list)


class InterviewSession(BaseModel):
    id: str
    owner_user_id: str
    title: str
    prompt: str
    state: SessionState
    candidate_editing_enabled: bool
    cursors_visible: bool
    scheduled_at: datetime | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    participants: list[Participant] = Field(default_factory=list)


class GuestLink(BaseModel):
    id: str
    session_id: str
    url: str
    role_granted: Role
    expires_at: datetime | None = None
    max_uses: int | None = None
    revoked_at: datetime | None = None
    created_at: datetime


# --------------------------- Canvas elements ---------------------------


class BaseElement(BaseModel):
    id: str
    x: float
    y: float
    z: float
    parent_id: str | None = None
    created_by: str
    created_at: datetime
    updated_at: datetime


class BoxElement(BaseElement):
    kind: Literal["component", "shape", "text", "sticky"]
    width: float
    height: float
    label: str
    description: str | None = None
    componentType: ComponentType | None = None
    shape: Literal["rect", "ellipse"] | None = None
    color: str | None = None


class StrokeElement(BaseElement):
    kind: Literal["stroke"]
    points: list[float]
    color: str
    width: float
    tool: Literal["pen", "highlighter"]


class ConnectorEndpoint(BaseModel):
    elementId: str | None = None
    x: float
    y: float


class ConnectorElement(BaseElement):
    model_config = ConfigDict(populate_by_name=True)

    kind: Literal["connector"]
    from_: ConnectorEndpoint = Field(alias="from")
    to: ConnectorEndpoint
    style: Literal["straight", "elbow", "curved"]
    dashed: bool
    color: str
    strokeWidth: float
    arrowStart: bool
    arrowEnd: bool
    label: str | None = None


CanvasElement = Union[BoxElement, StrokeElement, ConnectorElement]


class CanvasDocument(BaseModel):
    id: str
    session_id: str
    schema_version: int
    latest_operation_cursor: int
    updated_at: datetime
    elements: list[CanvasElement] = Field(default_factory=list)


# --------------------------- Requests / responses ---------------------------


class MagicLinkRequest(BaseModel):
    email: EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"


class SentResponse(BaseModel):
    sent: bool


class CreateSessionRequest(BaseModel):
    title: str
    prompt: str | None = None
    scheduled_at: datetime | None = None
    duration_minutes: int | None = None


class UpdateSessionRequest(BaseModel):
    title: str | None = None
    prompt: str | None = None
    candidate_editing_enabled: bool | None = None
    cursors_visible: bool | None = None
    state: SessionState | None = None


class CreateGuestLinkRequest(BaseModel):
    role_granted: Role | None = None
    expires_at: datetime | None = None
    max_uses: int | None = None


class JoinPreview(BaseModel):
    session_title: str
    joinable: bool
    reason: str | None = None


class JoinRequest(BaseModel):
    display_name: str


class JoinResponse(BaseModel):
    session: InterviewSession
    participant: Participant
    collaboration_token: str


class CanvasGetResponse(BaseModel):
    document: CanvasDocument
    collaboration_token: str
    websocket_url: str


class SavedAtResponse(BaseModel):
    saved_at: datetime
