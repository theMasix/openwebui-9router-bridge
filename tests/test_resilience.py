"""Test error handling, retries, and probe endpoints."""

import httpx
import pytest
import respx
from httpx import Response


@pytest.mark.asyncio
@respx.mock
async def test_retry_on_transient_error_and_recovery(app_and_client):
    """Verify bridge retries transient 500 error and recovers on next attempt."""
    _, client = app_and_client

    mock_route = respx.post("http://test-9router:20128/v1/search")
    mock_route.side_effect = [
        Response(503, text="Service Unavailable"),
        Response(200, json={"results": [{"title": "Success", "url": "https://ok.com"}]}),
    ]

    response = await client.post("/search", json={"query": "test retry"})
    assert response.status_code == 200
    assert mock_route.call_count == 2
    assert response.json()[0]["title"] == "Success"


@pytest.mark.asyncio
@respx.mock
async def test_retry_exhaustion_returns_502(app_and_client):
    """Verify bridge returns 502 Bad Gateway when all retries fail."""
    _, client = app_and_client

    mock_route = respx.post("http://test-9router:20128/v1/search").mock(
        return_value=Response(500, text="Internal Router Error")
    )

    response = await client.post("/search", json={"query": "test failure"})
    assert response.status_code == 502
    assert mock_route.called
    assert "9Router returned status 500" in response.json()["detail"]


@pytest.mark.asyncio
@respx.mock
async def test_connection_error_returns_504(app_and_client):
    """Verify bridge returns 504 when upstream connection fails."""
    _, client = app_and_client

    mock_route = respx.post("http://test-9router:20128/v1/search")
    mock_route.side_effect = httpx.ConnectError("Connection refused")

    response = await client.post("/search", json={"query": "timeout test"})
    assert response.status_code == 504
    assert "Failed to connect to 9Router" in response.json()["detail"]


@pytest.mark.asyncio
async def test_healthz_endpoint(app_and_client):
    """Verify liveness probe returns 200 OK."""
    _, client = app_and_client
    response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
@respx.mock
async def test_readyz_endpoint_healthy(app_and_client):
    """Verify readiness probe returns 200 when 9Router responds."""
    _, client = app_and_client
    respx.get("http://test-9router:20128/api/health").mock(
        return_value=Response(200, json={"ok": True})
    )

    response = await client.get("/readyz")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


@pytest.mark.asyncio
@respx.mock
async def test_readyz_endpoint_unhealthy(app_and_client):
    """Verify readiness probe returns 503 when 9Router is unreachable."""
    _, client = app_and_client
    respx.get("http://test-9router:20128/api/health").mock(
        side_effect=httpx.ConnectError("Unreachable")
    )
    respx.get("http://test-9router:20128/v1/models").mock(
        side_effect=httpx.ConnectError("Unreachable")
    )

    response = await client.get("/readyz")
    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
