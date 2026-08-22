"""SQLAlchemy engine/session setup and ORM table definitions.

Which database the server talks to is controlled entirely by the
DATABASE_URL environment variable (see app/main.py), in SQLAlchemy's own URL
format — defaults to a local SQLite file for zero-config dev/demo use.
Column types below are deliberately generic (String/Boolean/DateTime/JSON)
rather than SQLite-specific, so pointing DATABASE_URL at e.g.
`postgresql+psycopg2://...` later needs no schema changes, just installing
the driver.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, TypeDecorator, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
from sqlalchemy.pool import StaticPool

DEFAULT_DATABASE_URL = "sqlite:///./canvas_connect.db"


class UTCDateTime(TypeDecorator):
    """A timezone-aware DateTime that's actually portable.

    SQLite has no native timezone-aware type — it silently drops tzinfo on
    the way in and hands back naive datetimes on the way out, even though
    the column is declared `DateTime(timezone=True)`. Postgres's timestamptz
    doesn't have this problem. Rather than special-case SQLite, normalize
    both directions to UTC-aware here so callers (e.g. comparisons against
    `datetime.now(timezone.utc)`) never have to think about which backend
    they're on.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value


class Base(DeclarativeBase):
    pass


class UserRow(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String)
    organization_id: Mapped[str | None] = mapped_column(String, nullable=True)
    password_hash: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())


class SessionRow(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String)
    prompt: Mapped[str] = mapped_column(String)
    state: Mapped[str] = mapped_column(String)
    candidate_editing_enabled: Mapped[bool] = mapped_column(Boolean)
    cursors_visible: Mapped[bool] = mapped_column(Boolean)
    scheduled_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime())

    participants: Mapped[list["ParticipantRow"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ParticipantRow.joined_at",
    )


class ParticipantRow(Base):
    __tablename__ = "participants"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(String, ForeignKey("sessions.id"))
    user_id: Mapped[str | None] = mapped_column(String, ForeignKey("users.id"), nullable=True)
    display_name: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String)
    color: Mapped[str] = mapped_column(String)
    joined_at: Mapped[datetime] = mapped_column(UTCDateTime())
    left_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    connection_state: Mapped[str | None] = mapped_column(String, nullable=True)
    cursor: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    selection: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    session: Mapped[SessionRow] = relationship(back_populates="participants")


class GuestLinkRow(Base):
    __tablename__ = "guest_links"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(String, ForeignKey("sessions.id"))
    url: Mapped[str] = mapped_column(String)
    token_hash: Mapped[str] = mapped_column(String, unique=True, index=True)
    role_granted: Mapped[str] = mapped_column(String)
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    max_uses: Mapped[int | None] = mapped_column(Integer, nullable=True)
    use_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())


class CanvasDocumentRow(Base):
    __tablename__ = "canvas_documents"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(String, ForeignKey("sessions.id"), unique=True)
    schema_version: Mapped[int] = mapped_column(Integer)
    latest_operation_cursor: Mapped[int] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime())
    elements: Mapped[list] = mapped_column(JSON, default=list, nullable=False)


class TokenRow(Base):
    __tablename__ = "tokens"

    # The raw bearer token is the primary key, same as the old `self.tokens`
    # dict was keyed by the raw token — behavior-preserving, not a security
    # change (guest-link tokens, unlike these, are already stored hashed).
    token: Mapped[str] = mapped_column(String, primary_key=True)
    subject: Mapped[str] = mapped_column(String)
    user_id: Mapped[str | None] = mapped_column(String, nullable=True)
    participant_id: Mapped[str | None] = mapped_column(String, nullable=True)
    session_id: Mapped[str | None] = mapped_column(String, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())


def get_engine(database_url: str) -> Engine:
    connect_args: dict = {}
    engine_kwargs: dict = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        if ":memory:" in database_url:
            # A single shared connection, so every Session sees the same
            # in-memory database — otherwise each connection would get its
            # own empty one. Standard pattern for testing with SQLite.
            engine_kwargs["poolclass"] = StaticPool
    else:
        # Postgres (or any networked DB) connections can go stale — e.g. the
        # server closing idle ones — in a way a local SQLite file never does;
        # pre_ping catches that with a cheap check-out probe instead of
        # surfacing it as a query failure.
        engine_kwargs["pool_pre_ping"] = True
    return create_engine(database_url, connect_args=connect_args, **engine_kwargs)


def create_session_factory(engine: Engine) -> sessionmaker:
    Base.metadata.create_all(engine)
    # expire_on_commit=True (the default) matters here: Store's Session is
    # shared and long-lived (one per app, not one per request), so without
    # it, an already-loaded relationship (e.g. SessionRow.participants)
    # would keep serving stale in-memory data after a later commit changes
    # the underlying rows out from under it.
    return sessionmaker(bind=engine)
