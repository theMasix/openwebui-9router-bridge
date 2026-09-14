"""Pytest fixtures for bridge test suite."""

import pytest
from httpx import ASGITransport, AsyncClient

from bridge.client import NineRouterClient
from bridge.config import Settings
from bridge.main import create_app


@pytest.fixture
def base_settings() -> Settings:
    """Standard settings with predictable test defaults."""
    return Settings(
        bridge_host="127.0.0.1",
        bridge_port=8000,
        bridge_log_level="DEBUG",
        inbound_api_key=None,
        ninerouter_url="http://test-9router:20128",
        ninerouter_api_key="test-9router-secret",
        search_model="tavily",
        timeout_seconds=5.0,
        max_retries=2,
    )


@pytest.fixture
async def app_and_client(base_settings: Settings):
    """Create test application and HTTP client with mocked 9Router client."""
    app = create_app(base_settings)
    ninerouter_client = NineRouterClient(base_settings)
    app.state.ninerouter_client = ninerouter_client

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield app, client

    await ninerouter_client.close()
