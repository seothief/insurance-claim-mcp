FROM ghcr.io/astral-sh/uv:0.9.7 AS uv
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PATH="/app/.venv/bin:$PATH"
WORKDIR /app
COPY --from=uv /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
RUN test -r /etc/ssl/certs/ca-certificates.crt \
    && uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable \
    && useradd --uid 10002 --create-home v2app
USER v2app
ENV PORT=8080 V2_ENVIRONMENT=production
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/api/ready' % os.environ.get('PORT','8080'), timeout=4)" || exit 1
CMD ["sh", "-c", "exec uvicorn claim_mcp_v2.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips=*"]
