"""Main application factory and entrypoint for OpenWebUI-9Router bridge."""

import logging
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
import uvicorn
from fastapi import FastAPI

from bridge.client import NineRouterClient
from bridge.config import Settings, get_settings
from bridge.routes import router


def setup_logging(log_level: str) -> None:
    """Configure structured JSON logging with structlog."""
    level = getattr(logging, log_level.upper(), logging.INFO)

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application resources during lifecycle."""
    settings = get_settings()
    setup_logging(settings.log_level)
    logger = structlog.get_logger(__name__)

    logger.info(
        "starting_bridge",
        ninerouter_url=settings.ninerouter_url,
        search_model=settings.search_model,
        inbound_auth_enabled=bool(settings.inbound_api_key),
    )

    client = NineRouterClient(settings)
    app.state.ninerouter_client = client

    try:
        yield
    finally:
        logger.info("shutting_down_bridge")
        await client.close()


def create_app(settings: Settings | None = None) -> FastAPI:
    """FastAPI application factory."""
    resolved_settings = settings or get_settings()

    app = FastAPI(
        title="OpenWebUI-9Router Bridge",
        description="Translation bridge between Open WebUI search format and 9Router API",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    app.include_router(router)
    return app


app = create_app()


def run() -> None:
    """CLI execution entrypoint."""
    settings = get_settings()
    uvicorn.run(
        "bridge.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        access_log=False,
    )


if __name__ == "__main__":
    run()
