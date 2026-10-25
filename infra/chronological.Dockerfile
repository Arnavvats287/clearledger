# Build ONLY with scripts/build_chronological_image.py's allowlisted context.
FROM python:3.12-slim-bookworm
WORKDIR /app
ENV PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1 UV_CACHE_DIR=/tmp/uv-cache
RUN pip install --no-cache-dir uv==0.13.5
COPY pyproject.toml uv.lock .python-version ./
COPY src ./src
RUN uv sync --frozen --no-dev --no-cache
COPY alembic.ini ./
COPY infra/migrations ./infra/migrations
COPY scripts ./scripts
RUN mkdir /state && chown 10001:10001 /state
USER 10001:10001
ENV PATH=/app/.venv/bin:$PATH CL_ADAPTER_OUTPUT=/state/run
ENTRYPOINT ["python", "scripts/chronological_adapter.py"]
