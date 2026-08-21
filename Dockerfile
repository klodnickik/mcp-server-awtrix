# syntax=docker/dockerfile:1
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies and uv for fast, reliable package resolution
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

# Copy dependency specifications
COPY pyproject.toml .

# Install dependencies into a virtual environment
RUN uv venv /app/.venv
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="/app/.venv/bin:$PATH"
RUN uv pip install -e .

# Final runtime image
FROM python:3.12-slim AS runtime

WORKDIR /app

# Create non-root user for security
RUN groupadd -g 1000 appuser && \
    useradd -u 1000 -g appuser -s /bin/bash -m appuser

# Copy virtualenv from builder
COPY --from=builder /app/.venv /app/.venv
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Copy source code and app definitions
COPY pyproject.toml README.md .
COPY awtrix_mcp/ ./awtrix_mcp/
COPY apps/ ./apps/

# Set ownership
RUN chown -R appuser:appuser /app

USER appuser

# Default environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APPS_DIR=/app/apps \
    MCP_TRANSPORT=sse \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8000

EXPOSE 8000

# Default command runs the daemon (can be overridden to run MCP server)
CMD ["python", "-m", "awtrix_mcp.daemon"]
