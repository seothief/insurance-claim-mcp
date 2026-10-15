# Production image for the claim service (FastAPI REST + MCP over streamable HTTP).
# Works on Cloud Run (honours $PORT) and locally via docker compose.
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.lock.txt ./
# The lock file pins Windows-only packages (pywin32). Strip them so the Linux image installs.
RUN grep -viE '^(pywin32|pywin32-ctypes)' requirements.lock.txt > requirements.linux.txt \
    && pip install -r requirements.linux.txt

COPY src ./src

RUN useradd --create-home --uid 10001 appuser
USER appuser

ENV PORT=8080
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/api/health' % os.environ.get('PORT','8080'), timeout=4)" || exit 1

CMD ["sh", "-c", "uvicorn claim_service.main:app --app-dir src --host 0.0.0.0 --port ${PORT}"]
