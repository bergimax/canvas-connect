import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import DEFAULT_DATABASE_URL, create_session_factory, get_engine
from .errors import register_exception_handlers
from .frontend_proxy import register_frontend_proxy
from .routers import auth, canvas, guest_links, join, participants, sessions
from .store import Store


def create_app(database_url: str | None = None) -> FastAPI:
    app = FastAPI(title="Canvas Connect API", version="1.0.0")

    # DATABASE_URL is any SQLAlchemy URL (e.g. postgresql+psycopg2://...);
    # defaults to a local SQLite file so the app runs with zero setup.
    database_url = database_url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    engine = get_engine(database_url)
    session_factory = create_session_factory(engine)
    app.state.store = Store(session_factory())

    register_exception_handlers(app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth.router)
    app.include_router(sessions.router)
    app.include_router(guest_links.router)
    app.include_router(join.router)
    app.include_router(canvas.router)
    app.include_router(participants.router)

    # Catch-all, must stay last: anything not matched by a /v1 route above
    # falls through to the frontend (see frontend_proxy.py).
    register_frontend_proxy(app)

    return app


app = create_app()
