# syntax=docker/dockerfile:1.7
# The test runner image. Deliberately browser-less: browsers live in Selenium Grid containers
# (compose.yaml) or on the CI runner, so the same image drives Chrome, Firefox or Edge and stays
# small. Dependencies come from uv.lock — the same pinned set as CI and developer machines.
# Runs as a non-root user; the run directory is a mounted volume.

FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
# Dependencies first — this layer is cached until uv.lock changes — then the project itself.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-editable
COPY pyproject.toml uv.lock ./
COPY streamcart ./streamcart
COPY streamcart_pytest ./streamcart_pytest
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-editable

FROM python:3.12-slim AS runtime
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STREAMCART_TARGET=chrome-grid \
    STREAMCART_WEB__REMOTE_URL=http://selenium:4444
RUN useradd --create-home --uid 1000 streamcart
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --chown=streamcart:streamcart . .
RUN mkdir -p /app/reports && chown -R streamcart:streamcart /app
USER streamcart
HEALTHCHECK NONE
ENTRYPOINT ["pytest", "tests/steps"]
CMD ["--platform", "web", "-n", "2", "-ra"]
