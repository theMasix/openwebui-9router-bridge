"""Test protocol mapping and conversion between OpenWebUI and 9Router schemas."""

import json

import pytest
import respx
from httpx import Response
from pydantic import ValidationError

from bridge.schemas import (
    NineRouterResultItem,
    NineRouterSearchResponse,
    OpenWebUISearchRequest,
    map_ninerouter_to_openwebui,
)


def test_openwebui_request_validation():
    """Verify request validation rules."""
    req = OpenWebUISearchRequest(query="test query")
    assert req.query == "test query"
    assert req.count == 5

    req_custom = OpenWebUISearchRequest(query="deep search", count=10)
    assert req_custom.count == 10

    with pytest.raises(ValidationError):
        OpenWebUISearchRequest(query="")


def test_schema_mapping_logic():
    """Verify conversion from 9Router response schema to OpenWebUI format."""
    nine_resp = NineRouterSearchResponse(
        provider="tavily",
        query="test query",
        results=[
            NineRouterResultItem(
                title="Example Domain",
                url="https://example.com",
                snippet="Informative snippet",
                display_url="example.com",
                score=0.95,
            ),
            NineRouterResultItem(
                title=None,
                url=None,
                display_url="https://fallback.com",
                snippet=None,
            ),
        ],
    )

    openwebui_results = map_ninerouter_to_openwebui(nine_resp)
    assert len(openwebui_results) == 2

    first = openwebui_results[0]
    assert first.link == "https://example.com"
    assert first.title == "Example Domain"
    assert first.snippet == "Informative snippet"

    second = openwebui_results[1]
    assert second.link == "https://fallback.com"
    assert second.title == ""
    assert second.snippet == ""


@pytest.mark.asyncio
@respx.mock
async def test_search_endpoint_full_translation(app_and_client):
    """Verify end-to-end request/response translation via HTTP."""
    _, client = app_and_client

    mock_upstream_response = {
        "provider": "tavily",
        "query": "kubernetes best practices",
        "results": [
            {
                "title": "K8s Guide",
                "url": "https://kubernetes.io/docs/concepts/",
                "snippet": "Kubernetes architectural concepts.",
            },
            {
                "title": "Production Checklist",
                "url": "https://learnk8s.io/production-best-practices",
                "snippet": "Detailed production checklist.",
            },
        ],
    }

    mock_route = respx.post("http://test-9router:20128/v1/search").mock(
        return_value=Response(200, json=mock_upstream_response)
    )

    response = await client.post(
        "/search",
        json={"query": "kubernetes best practices", "count": 2},
    )

    assert response.status_code == 200
    assert mock_route.called

    # Check request received by 9Router
    sent_request = json.loads(mock_route.calls.last.request.content)
    assert sent_request["model"] == "tavily"
    assert sent_request["query"] == "kubernetes best practices"
    assert sent_request["max_results"] == 2

    # Check response returned to OpenWebUI
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["link"] == "https://kubernetes.io/docs/concepts/"
    assert data[0]["title"] == "K8s Guide"
    assert data[0]["snippet"] == "Kubernetes architectural concepts."
