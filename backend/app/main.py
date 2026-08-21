from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .errors import register_exception_handlers
from .routers import auth, canvas, guest_links, join, participants, sessions
from .store import Store


def create_app() -> FastAPI:
    app = FastAPI(title="Canvas Connect API", version="1.0.0")
    app.state.store = Store()

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

    return app


app = create_app()
