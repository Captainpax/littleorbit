"""FastAPI application factory and route assembly."""

from datetime import timedelta

from fastapi import FastAPI
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from .client_compatibility import AndroidCompatibilityMiddleware
from .notes_hub import NoteConnectionHub
from .rate_limit import FixedWindowLimiter
from .routes import (
    account,
    admin,
    admin_console,
    auth,
    countdowns,
    couples,
    health,
    locations,
    notes,
    pairing,
    quizzes,
    quizzes_v2,
    releases,
    together_time_v2,
)


def create_app() -> FastAPI:
    """Create the Little Orbit ASGI application without hidden side effects."""

    app = FastAPI(
        title="Little Orbit API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url=None,
        openapi_url="/openapi.json",
    )
    app.state.note_connections = NoteConnectionHub()
    app.state.registration_ip_limiter = FixedWindowLimiter(
        limit=8, window=timedelta(hours=1)
    )
    app.state.registration_email_limiter = FixedWindowLimiter(
        limit=4, window=timedelta(hours=1)
    )
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=[
            "lil-orb.pax-kun.com",
            "192.168.50.182",
            "localhost",
            "127.0.0.1",
            "api",
        ],
    )
    app.add_middleware(AndroidCompatibilityMiddleware)
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(pairing.router)
    app.include_router(couples.router)
    app.include_router(quizzes.router)
    app.include_router(quizzes_v2.router)
    app.include_router(countdowns.router)
    app.include_router(locations.router)
    app.include_router(together_time_v2.router)
    app.include_router(account.router)
    app.include_router(releases.router)
    app.include_router(admin.router)
    app.include_router(admin_console.router)
    app.include_router(notes.router)
    return app


app = create_app()
