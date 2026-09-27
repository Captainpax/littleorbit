"""FastAPI application factory and route assembly."""

from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from .client_compatibility import AndroidCompatibilityMiddleware
from .config import Settings, get_settings
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
    big_orbit_bootstrap,
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
    quizzes_v4,
    relationship_names,
    releases,
    smooches,
    together_time_details,
    together_time_legacy,
    together_time_v2,
)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the Little Orbit ASGI application without hidden side effects."""

    runtime = settings or get_settings()
    app = FastAPI(
        title="Little Orbit API",
        version="1.3.0",
        docs_url="/docs",
        redoc_url=None,
        openapi_url="/openapi.json",
    )
    app.state.note_connections = NoteConnectionHub()
    app.state.notification_connections = NotificationConnectionHub()
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=_trusted_hosts(runtime),
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
    app.include_router(quizzes_v4.router)
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
    app.include_router(big_orbit_bootstrap.router)
    app.include_router(big_orbit_console.router)
    app.include_router(notes.router)
    app.include_router(note_forks.router)
    app.include_router(notifications.router)
    app.include_router(attachments.router)
    app.include_router(archive_attachments.router)
    app.include_router(smooches.router)
    return app


def _trusted_hosts(settings: Settings) -> list[str]:
    """Allow only the configured public origin and bounded local service names."""

    hostname = urlsplit(settings.public_base_url).hostname
    if hostname is None:
        raise ValueError("PUBLIC_BASE_URL must be an absolute URL with a hostname")
    return list(dict.fromkeys((hostname, "localhost", "127.0.0.1", "api")))


app = create_app()
