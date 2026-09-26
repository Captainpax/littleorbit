"""Terminal responses for together-time contracts retired before 1.0."""

from fastapi import APIRouter, HTTPException, status

router = APIRouter(tags=["together-time-retired"])


def _gone() -> None:
    """Return one content-free retirement response for every legacy method."""

    raise HTTPException(
        status.HTTP_410_GONE,
        {"code": "route_retired", "message": "Update Little Orbit to continue"},
    )


@router.api_route(
    "/v1/together-time",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
)
@router.api_route(
    "/v1/together-time/{remainder:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
)
@router.api_route(
    "/v2/together-time",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
)
@router.api_route(
    "/v2/together-time/{remainder:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
)
async def retired_together_time(remainder: str = "") -> None:
    """Reject a legacy request without reading account or relationship state."""

    del remainder
    _gone()
