# CONTROL LAYER — the Telegram bot. Runs on the VPS.
#
# Build context is new_implementation/. Only the bot package and its two
# dependencies go in (requirements-bot.txt): no engine, no SQLAlchemy, no
# FastAPI, no database URL. The bot is a thin client over the API on the home
# server, reached over WireGuard, and its only local state is the durable
# outbox in /data (a named volume) -- the queue that guarantees a player's
# orders and messages survive the tunnel being down.
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src \
    DIPLOMACY_BOT_DATA_DIR=/data \
    DIPLOMACY_BOT_HEARTBEAT=/tmp/diplomacy-bot-heartbeat

WORKDIR /app

COPY requirements-bot.txt .
RUN pip install -r requirements-bot.txt

RUN adduser --disabled-password --gecos "" app \
    && mkdir -p /data && chown app:app /data

# The bot is the `server.telegram_bot` package; `server/__init__.py` is empty
# and only needed so the package path resolves.
COPY --chown=app:app src/server/__init__.py ./src/server/__init__.py
COPY --chown=app:app src/server/telegram_bot ./src/server/telegram_bot

USER app
VOLUME ["/data"]

# Both background loops touch the heartbeat file every few seconds. If it goes
# stale the process is wedged (or never started its loops) and Docker restarts it.
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD test -f "$DIPLOMACY_BOT_HEARTBEAT" && \
        test $(( $(date +%s) - $(stat -c %Y "$DIPLOMACY_BOT_HEARTBEAT") )) -lt 120

CMD ["python", "-m", "server.telegram_bot"]
