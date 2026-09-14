# Build stage using uv
FROM python:3.12-slim AS builder

WORKDIR /build

# Install uv from official Astral image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy project specification files
COPY pyproject.toml .python-version ./

# Install dependencies into a virtual environment using uv
RUN uv venv /app/.venv && \
    uv pip install --no-cache -r pyproject.toml

# Runtime stage
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for audio processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application source code
COPY src/ /app/src/
COPY pyproject.toml ./

# Create non-root user for security hardening
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Health check probe using standard library urllib
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Expose API port
EXPOSE 8000

# Default command - start FastAPI server with Uvicorn
CMD ["uvicorn", "ethos.interfaces:app", "--host", "0.0.0.0", "--port", "8000"]
