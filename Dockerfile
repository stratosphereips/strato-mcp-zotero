# syntax=docker/dockerfile:1

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY src/ src/

RUN uv sync --frozen --no-dev

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src

RUN useradd --uid 1000 --no-create-home --shell /bin/sh appuser

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

USER appuser

LABEL org.opencontainers.image.title="zotero-mcp" \
      org.opencontainers.image.description="MCP server exposing the Zotero Web API as tools for AI assistants" \
      org.opencontainers.image.source="https://github.com/stratosphereips/strato-mcp-zotero" \
      org.opencontainers.image.version="0.1.0" \
      org.opencontainers.image.licenses="GPL-2.0"

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["serve"]
