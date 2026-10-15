# The FastAPI server.
#
# Build context is the repository root. The image carries the engine, the
# renderer (needs libcairo2), the DAL, and the Alembic migrations, which the
# entrypoint applies before uvicorn starts. It deliberately does NOT carry the
# Telegram token: the API never talks to Telegram. It writes notifications to
# the bot_outbox table and the bot container pulls them.
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
COPY --chown=app:app src ./src
COPY --chown=app:app docker/api-entrypoint.sh /usr/local/bin/api-entrypoint.sh
RUN chmod +x /usr/local/bin/api-entrypoint.sh

USER app

EXPOSE 8000 8432

# bash's /dev/tcp makes the probe a plain HTTP request with no interpreter
# start-up (python:3.14-slim has neither curl nor wget). It passes only on a
# "200" status line. --start-interval polls fast until the first success (needs
# Docker Engine >= 25), then --interval applies.
HEALTHCHECK --interval=60s --timeout=5s --start-period=40s --start-interval=2s --retries=3 \
    CMD ["bash", "-c", "exec 3<>/dev/tcp/127.0.0.1/8000 && printf 'GET /healthz HTTP/1.0\\r\\nHost: localhost\\r\\n\\r\\n' >&3 && read -r status <&3 && case \"$status\" in *' 200 '*) exit 0;; esac; exit 1"]

ENTRYPOINT ["/usr/local/bin/api-entrypoint.sh"]
