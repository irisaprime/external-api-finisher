# ============================================================================
# Stage 1: Builder - Install dependencies with uv
# ============================================================================
FROM python:3.11-slim AS builder

ARG VERSION=1.0.0
ARG BUILD_DATE
ARG VCS_REF

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    libpq-dev \
    postgresql-client \
    make \
    && rm -rf /var/lib/apt/lists/*

ENV UV_VERSION=0.8.17
RUN curl -LsSf https://astral.sh/uv/${UV_VERSION}/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev --no-editable

# ============================================================================
# Stage 2: Production - Minimal runtime image
# ============================================================================
FROM python:3.11-slim AS production


LABEL maintainer="Arash Team <team@example.com>" \
      version="1.0.0" \
      description="Arash External API Service - Multi-platform AI chatbot with integrated Telegram bot" \
      org.opencontainers.image.title="Arash Bot" \
      org.opencontainers.image.description="Multi-platform AI chatbot with channel-based access control" \
      org.opencontainers.image.version="1.0.0" \
      org.opencontainers.image.vendor="Arash Team"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    postgresql-client \
    curl \
    make \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 appuser && \
    mkdir -p /app /app/logs && \
    chown -R appuser:appuser /app

WORKDIR /app

COPY --from=builder /build/.venv /app/.venv

ENV VIRTUAL_ENV=/app/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

COPY --chown=appuser:appuser . .

RUN mkdir -p logs && chown -R appuser:appuser logs

USER appuser

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:3000/health || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "3000", "--no-access-log"]
