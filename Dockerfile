# One image for the API, the worker and the built web: one Cloud Run service, one URL (issue #86).
# Build: docker build -t review-analyzer .   Run: docker run --env-file .env -p 8080:8080 review-analyzer

FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.12-slim AS deps
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv
WORKDIR /srv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.12-slim
RUN useradd --system --uid 10001 --no-create-home app
WORKDIR /srv
COPY --from=deps /srv/.venv /srv/.venv
COPY app/ ./app/
COPY --from=web /web/dist ./web
ENV PATH="/srv/.venv/bin:$PATH" PYTHONUNBUFFERED=1 WEB_DIR=/srv/web PORT=8080
USER app
EXPOSE 8080
CMD ["sh", "-c", "exec uvicorn --factory app.main:service_app --host 0.0.0.0 --port ${PORT}"]
