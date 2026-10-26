FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
ENV CHROME_BIN=/usr/bin/chromium CHROME_PATH=/usr/bin/chromium CHROMIUM_PATH=/usr/bin/chromium

# Install Chromium and system dependencies for headless browser automation
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    fonts-liberation \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv/life-sandbox
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv && uv sync --locked --no-dev --extra browser
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /srv/life-sandbox/data/uploads /tmp/life-sandbox-browser-use \
    && chown -R appuser:appuser /srv/life-sandbox /tmp/life-sandbox-browser-use
USER appuser
EXPOSE 8000
CMD [".venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
