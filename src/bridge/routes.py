"""HTTP route handlers for search protocol translation and health checks."""

from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status

from bridge.config import Settings, get_settings
from bridge.schemas import (
    OpenWebUISearchRequest,
    OpenWebUISearchResult,
    map_ninerouter_to_openwebui,
)

logger = structlog.get_logger(__name__)
router = APIRouter()


async def verify_inbound_auth(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    """Validate Bearer token from OpenWebUI if inbound authentication is required."""
    settings: Settings = getattr(request.app.state, "settings", None) or get_settings()

    if not settings.inbound_api_key:
        return

    expected_header = f"Bearer {settings.inbound_api_key}"
    if not authorization or authorization.strip() != expected_header:
        logger.warning("unauthorized_request_rejected")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: invalid or missing Bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post(
    "/search",
    response_model=list[OpenWebUISearchResult],
    summary="Search web via 9Router",
    dependencies=[Depends(verify_inbound_auth)],
)
async def search_endpoint(
    request: Request,
    payload: OpenWebUISearchRequest,
) -> list[OpenWebUISearchResult]:
    """Translate OpenWebUI external search request and forward to 9Router."""
    client = request.app.state.ninerouter_client

    logger.info("incoming_search", query=payload.query, count=payload.count)
    nine_response = await client.search(
        query=payload.query,
        max_results=payload.count,
    )

    results = map_ninerouter_to_openwebui(nine_response)
    logger.info("search_completed", returned_results=len(results))
    return results


@router.get("/healthz", summary="Liveness check")
async def healthz() -> dict[str, str]:
    """Kubernetes liveness probe endpoint."""
    return {"status": "ok"}


@router.get("/readyz", summary="Readiness check")
async def readyz(
    request: Request,
    response: Response,
) -> dict[str, Any]:
    """Kubernetes readiness probe endpoint verifying 9Router connection."""
    client = getattr(request.app.state, "ninerouter_client", None)
    if client is None:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not_ready", "detail": "Client not initialized"}

    upstream_ok = await client.check_health()
    if not upstream_ok:
        logger.warning("readiness_check_upstream_unavailable")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "degraded", "upstream_healthy": False}

    return {"status": "ready", "upstream_healthy": True}
