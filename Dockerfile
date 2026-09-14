# Multi-stage build leveraging official uv binary for fast reproducible installs
FROM ghcr.io/astral-sh/uv:0.6.5-python3.12-bookworm-slim AS builder

WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Install dependencies first (cached across builds)
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

# Copy source and build package
COPY pyproject.toml uv.lock README.md LICENSE /app/
COPY src/ /app/src/

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Final runtime image
FROM python:3.12-slim-bookworm AS runtime

LABEL maintainer="Masih"
LABEL description="OpenWebUI to 9Router Search Bridge"

# Create non-root user
RUN groupadd -g 10001 bridge && \
    useradd -u 10001 -g 10001 -r -s /bin/false -d /app bridge

WORKDIR /app

# Copy virtual environment and application
COPY --from=builder --chown=bridge:bridge /app/.venv /app/.venv
COPY --from=builder --chown=bridge:bridge /app/src /app/src

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

USER 10001:10001

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
  CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz').read()" || exit 1

ENTRYPOINT ["openwebui-9router-bridge"]
