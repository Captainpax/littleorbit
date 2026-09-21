"""FastAPI application factory and route assembly."""

from fastapi import FastAPI
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from .client_compatibility import AndroidCompatibilityMiddleware
from .notes_hub import NoteConnectionHub
from .notification_hub import NotificationConnectionHub
from .routes import (
    account,
    activity,
    admin,
    admin_console,
    archive_attachments,
    attachments,
    auth,
    big_orbit_auth,
    big_orbit_console,
    countdowns,
    couples,
    diagnostics,
    health,
    note_forks,
    notes,
    notifications,
    pairing,
    profile_photos,
    quizzes,
    quizzes_v2,
    quizzes_v3,
    relationship_names,
    releases,
    smooches,
    together_time_details,
    together_time_legacy,
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
    app.state.notification_connections = NotificationConnectionHub()
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
    app.include_router(diagnostics.router)
    app.include_router(quizzes.router)
    app.include_router(quizzes_v2.router)
    app.include_router(quizzes_v3.router)
    app.include_router(countdowns.router)
    app.include_router(together_time_legacy.router)
    app.include_router(together_time_v2.v3_router)
    app.include_router(together_time_details.router)
    app.include_router(account.router)
    app.include_router(activity.router)
    app.include_router(profile_photos.router)
    app.include_router(relationship_names.router)
    app.include_router(releases.router)
    app.include_router(admin.router)
    app.include_router(admin_console.router)
    app.include_router(big_orbit_auth.router)
    app.include_router(big_orbit_console.router)
    app.include_router(notes.router)
    app.include_router(note_forks.router)
    app.include_router(notifications.router)
    app.include_router(attachments.router)
    app.include_router(archive_attachments.router)
    app.include_router(smooches.router)
    return app


app = create_app()
