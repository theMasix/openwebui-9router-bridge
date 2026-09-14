"""Test inbound and outbound authentication handling."""

import pytest
import respx
from httpx import ASGITransport, AsyncClient, Response

from bridge.client import NineRouterClient
from bridge.config import Settings
from bridge.main import create_app


@pytest.mark.asyncio
@respx.mock
async def test_inbound_auth_enforcement():
    """Verify unauthorized requests are rejected when inbound_api_key is set."""
    settings = Settings(
        inbound_api_key="expected-openwebui-key",
        ninerouter_url="http://test-9router:20128",
        ninerouter_api_key="router-key",
        search_model="tavily",
    )

    app = create_app(settings)
    ninerouter_client = NineRouterClient(settings)
    app.state.ninerouter_client = ninerouter_client

    respx.post("http://test-9router:20128/v1/search").mock(
        return_value=Response(200, json={"results": []})
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Case 1: No auth header provided
        res_no_auth = await client.post("/search", json={"query": "test"})
        assert res_no_auth.status_code == 401

        # Case 2: Wrong bearer token provided
        res_wrong_auth = await client.post(
            "/search",
            json={"query": "test"},
            headers={"Authorization": "Bearer wrong-key"},
        )
        assert res_wrong_auth.status_code == 401

        # Case 3: Valid bearer token provided
        res_valid_auth = await client.post(
            "/search",
            json={"query": "test"},
            headers={"Authorization": "Bearer expected-openwebui-key"},
        )
        assert res_valid_auth.status_code == 200

    await ninerouter_client.close()


@pytest.mark.asyncio
@respx.mock
async def test_outbound_auth_header():
    """Verify bridge forwards correct bearer token to 9Router."""
    settings = Settings(
        inbound_api_key=None,
        ninerouter_url="http://test-9router:20128",
        ninerouter_api_key="super-secret-9router-token",
        search_model="brave",
    )

    app = create_app(settings)
    ninerouter_client = NineRouterClient(settings)
    app.state.ninerouter_client = ninerouter_client

    mock_route = respx.post("http://test-9router:20128/v1/search").mock(
        return_value=Response(200, json={"results": []})
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/search", json={"query": "test query"})
        assert res.status_code == 200

        sent_auth = mock_route.calls.last.request.headers.get("Authorization")
        assert sent_auth == "Bearer super-secret-9router-token"

    await ninerouter_client.close()
