"""Async HTTP client for 9Router search API with pooling and retries."""

import asyncio
from typing import Any

import httpx
import structlog
from fastapi import HTTPException, status

from bridge.config import Settings
from bridge.schemas import (
    NineRouterSearchRequest,
    NineRouterSearchResponse,
)

logger = structlog.get_logger(__name__)


class NineRouterClient:
    """Encapsulates async HTTP communication with 9Router."""

    def __init__(self, settings: Settings):
        self.base_url = settings.ninerouter_url.rstrip("/")
        self.api_key = settings.ninerouter_api_key
        self.default_model = settings.search_model
        self.timeout = settings.timeout_seconds
        self.max_retries = max(0, settings.max_retries)

        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=httpx.Timeout(self.timeout),
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
            trust_env=False,
        )

    async def close(self) -> None:
        """Close underlying HTTP client session."""
        await self._client.aclose()

    async def check_health(self) -> bool:
        """Ping 9Router /api/health or /v1/models to verify upstream availability."""
        try:
            resp = await self._client.get("/api/health", timeout=3.0)
            if resp.status_code == 200:
                return True
        except Exception:
            pass

        # Fallback check on models endpoint if /api/health is absent
        try:
            resp = await self._client.get("/v1/models", timeout=3.0)
            return resp.status_code == 200
        except Exception:
            return False

    async def search(
        self,
        query: str,
        max_results: int = 5,
        model: str | None = None,
    ) -> NineRouterSearchResponse:
        """Execute search on 9Router with retries for transient errors."""
        search_model = model or self.default_model
        req_payload = NineRouterSearchRequest(
            model=search_model,
            query=query,
            max_results=max_results,
        )

        url = "/v1/search"
        payload_dict: dict[str, Any] = req_payload.model_dump()

        attempt = 0
        last_error: Exception | None = None

        while attempt <= self.max_retries:
            try:
                logger.debug(
                    "sending_search_request",
                    model=search_model,
                    query=query,
                    max_results=max_results,
                    attempt=attempt + 1,
                )
                response = await self._client.post(url, json=payload_dict)

                if response.status_code == 200:
                    data = response.json()
                    return NineRouterSearchResponse.model_validate(data)

                # If upstream rate-limited (429) or server error (500, 502, 503, 504), retry
                if response.status_code in {429, 500, 502, 503, 504} and attempt < self.max_retries:
                    wait_time = 0.5 * (2 ** attempt)
                    logger.warning(
                        "upstream_transient_error_retrying",
                        status_code=response.status_code,
                        attempt=attempt + 1,
                        wait_seconds=wait_time,
                    )
                    await asyncio.sleep(wait_time)
                    attempt += 1
                    continue

                # Non-transient client error or retries exhausted
                err_text = response.text
                logger.error(
                    "upstream_error_response",
                    status_code=response.status_code,
                    body=err_text,
                )
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"9Router returned status {response.status_code}: {err_text}",
                )

            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                last_error = exc
                if attempt < self.max_retries:
                    wait_time = 0.5 * (2 ** attempt)
                    logger.warning(
                        "upstream_network_error_retrying",
                        error=str(exc),
                        attempt=attempt + 1,
                        wait_seconds=wait_time,
                    )
                    await asyncio.sleep(wait_time)
                    attempt += 1
                    continue
                break

        logger.error(
            "upstream_connection_failed",
            error=str(last_error),
            attempts=attempt + 1,
        )
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Failed to connect to 9Router at {self.base_url}: {last_error}",
        )
