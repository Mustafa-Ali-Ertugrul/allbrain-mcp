FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    ALLOWED_PROJECT_ROOTS=/app

WORKDIR /app

RUN apt-get update \
    && apt-get install --yes --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv

COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src

RUN uv sync --frozen --no-dev --no-editable

RUN useradd --create-home --uid 10001 allbrain \
    && chown -R allbrain:allbrain /app

USER allbrain

CMD ["uv", "run", "--no-sync", "allbrain", "start", "--project", "/app", "--agent", "glama", "--tool-profile", "minimal"]
