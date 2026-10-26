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
# -I ignores PYTHONPATH and the script directory. Register only the immutable,
# root-owned allowlisted harness directory as an installed site path (no code).
RUN /app/.venv/bin/python -I -B -c "import sysconfig; from pathlib import Path; Path(sysconfig.get_path('purelib'), 'clearledger_harness.pth').write_text('/app/scripts\n', encoding='utf-8')"
RUN mkdir /state && chown 10001:10001 /state
USER 10001:10001
ENV PATH=/app/.venv/bin:$PATH CL_ADAPTER_OUTPUT=/state/run
# Build-time EOF import preflight uses the operator's exact invocation, as UID10001.
RUN /app/.venv/bin/python -X utf8 -I -B /app/scripts/chronological_adapter.py < /dev/null
ENTRYPOINT ["/app/.venv/bin/python", "-X", "utf8", "-I", "-B", "/app/scripts/chronological_adapter.py"]
