# NOTE: release pipeline MUST replace the tag with a digest
# (`python:3.12-slim@sha256:<digest>`) before promotion. Constitution
# Principle VI requires digest pinning for shipped images.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --create-home app

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY fixtures ./fixtures

RUN uv sync --frozen --no-dev

USER 10001

ENV PORT=8080
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
    CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8080/healthz')"

CMD ["uv", "run", "--no-dev", "python", "-m", "cto_order_agent.main"]
