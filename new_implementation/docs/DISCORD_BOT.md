# Discord Bot

Optional Discord bot that uses the same Diplomacy backend API as the Telegram bot. It provides a minimal set of commands for listing games and viewing game status.

## Setup

1. **Create a Discord application and bot**
   - Go to [Discord Developer Portal](https://discord.com/developers/applications) → New Application.
   - In the application, open **Bot** → Add Bot. Copy the **Token** (this is `DIPLOMACY_DISCORD_BOT_TOKEN`).

2. **Invite the bot to your server**
   - In the Developer Portal: OAuth2 → URL Generator. Scopes: `bot`. Bot Permissions: e.g. Send Messages, Read Message History.
   - Open the generated URL and add the bot to your server.

3. **Environment variables**
   - `DIPLOMACY_DISCORD_BOT_TOKEN` — (required) Discord bot token.
   - `DIPLOMACY_API_URL` — (optional) Backend API base URL, default `http://localhost:8000`.
   - `DIPLOMACY_DISCORD_PREFIX` — (optional) Command prefix, default `!`.

## Running the bot

From the project root (with `src` on `PYTHONPATH`):

```bash
cd new_implementation
export DIPLOMACY_DISCORD_BOT_TOKEN=your_token_here
export DIPLOMACY_API_URL=http://localhost:8000   # if API is elsewhere
PYTHONPATH=.:src python -m server.run_discord_bot
# or:
PYTHONPATH=.:src python src/server/run_discord_bot.py
```

Ensure the Diplomacy API server is running and reachable at `DIPLOMACY_API_URL`.

## Commands

| Command        | Description                          |
|----------------|--------------------------------------|
| `!games`      | List all games (id, phase, player count). |
| `!status <game_id>` | Game status: phase and power summary.   |
| `!bothelp`    | Show Diplomacy bot command list and backend URL. |

Use the prefix set by `DIPLOMACY_DISCORD_PREFIX` (default `!`).

## Dependencies

- `discord.py>=2.0.0,<3.0.0` (in `requirements.txt`).

## Relation to Telegram bot

The Discord bot does not implement the full Telegram feature set (registration, join, orders, messages, maps). It is a minimal cross-platform viewer: same API, subset of read-only commands. Full gameplay is supported on Telegram and the browser client.
