# GAME LAYER — the FastAPI server. Runs on the HOME server (kattotuuletin).
#
# Build context is new_implementation/. The image carries the engine, the
# renderer (needs libcairo2), the DAL, and the Alembic migrations, which the
# entrypoint applies before uvicorn starts. It deliberately does NOT carry the
# Telegram token: the API never talks to Telegram. It writes notifications to
# the bot_outbox table and the bot on the VPS pulls them.
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src

# libcairo2 for CairoSVG (map rendering). libpq is bundled with psycopg2-binary.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libcairo2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

RUN adduser --disabled-password --gecos "" app \
    && mkdir -p /tmp/diplomacy_map_cache && chown app:app /tmp/diplomacy_map_cache

COPY --chown=app:app alembic.ini ./
COPY --chown=app:app alembic ./alembic
COPY --chown=app:app maps ./maps
COPY --chown=app:app icons ./icons
COPY --chown=app:app src ./src
COPY --chown=app:app docker/api-entrypoint.sh /usr/local/bin/api-entrypoint.sh
RUN chmod +x /usr/local/bin/api-entrypoint.sh

USER app

EXPOSE 8000 8432

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4).status == 200 else 1)"

ENTRYPOINT ["/usr/local/bin/api-entrypoint.sh"]
