FROM python:3.12-slim-bookworm AS build

RUN python -m pip install --no-cache-dir uv==0.12.15

ENV UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-install-project

COPY backend/src ./backend/src
RUN uv sync --locked --no-dev --no-editable

FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    DATABASE_PATH=/app/data/tradebridge.db

WORKDIR /app
RUN groupadd --gid 10001 tradebridge \
    && useradd --uid 10001 --gid tradebridge --no-create-home --shell /usr/sbin/nologin tradebridge \
    && mkdir -p /app/data \
    && chown tradebridge:tradebridge /app/data

COPY --from=build /app/.venv /app/.venv
USER tradebridge

EXPOSE 8000
# A single worker owns the in-process scheduler. Only Nginx reaches this port.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*"]
