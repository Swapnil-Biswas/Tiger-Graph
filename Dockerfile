# ==============================================================================
# Stage 1: Builder - Build dependencies in isolated virtual environment
# ==============================================================================
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir --upgrade pip && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# ==============================================================================
# Stage 2: Runtime - Minimal, hardened, non-root production container
# ==============================================================================
FROM python:3.11-slim AS runner

# Security hardening: create unprivileged system group and user
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/bash -m appuser

# Install minimal curl for container healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy virtualenv from builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ENVIRONMENT=production

# Copy application source code and assets
COPY --chown=appuser:appgroup src/ ./src/
COPY --chown=appuser:appgroup ui/ ./ui/
COPY --chown=appuser:appgroup eval/ ./eval/
COPY --chown=appuser:appgroup cases/ ./cases/
COPY --chown=appuser:appgroup data/ ./data/
COPY --chown=appuser:appgroup docs/ ./docs/
COPY --chown=appuser:appgroup requirements.txt ./

# Ensure runtime directories are writable by non-root user
RUN chown -R appuser:appgroup /app

# Switch to non-root user (CIS Docker Benchmark)
USER appuser

# Expose API and Web UI port
EXPOSE 8000

# Container Healthcheck targeting SLA telemetry endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/api/telemetry/dashboard || exit 1

# Launch production server with Uvicorn
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
