# Image for the API server (quantum_platform). Build from the repository root:
#   docker build -t quantum-platform .

FROM python:3.13-slim AS build

# uv installs exactly the versions pinned in uv.lock, so the image matches local development.
COPY --from=ghcr.io/astral-sh/uv:0.9.4 /uv /bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# The lock file covers the whole workspace, so both member packages must be present to resolve it.
COPY pyproject.toml uv.lock ./
COPY sdk ./sdk
COPY server ./server

# Install only the server package and its runtime dependencies into /app/.venv.
RUN uv sync --frozen --no-dev --no-editable --package quantum-platform


FROM python:3.13-slim

# Run as an unprivileged user; /data holds the SQLite file.
RUN useradd --create-home --uid 1000 app && mkdir /data && chown app:app /data
COPY --from=build --chown=app:app /app/.venv /app/.venv

USER app
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    QP_DB_PATH=/data/quantum.db

EXPOSE 8000

# Healthy only when storage is reachable and the workers are running (GET /ready returns 200).
HEALTHCHECK --interval=5s --timeout=3s --start-period=5s --retries=5 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=2)"]

CMD ["uvicorn", "quantum_platform.main:app", "--host", "0.0.0.0", "--port", "8000"]
