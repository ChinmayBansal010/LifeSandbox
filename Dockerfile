FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv/life-sandbox
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv && uv sync --locked --no-dev
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./
RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /srv/life-sandbox
USER appuser
EXPOSE 8000
CMD [".venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
