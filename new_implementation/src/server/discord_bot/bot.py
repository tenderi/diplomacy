"""
Discord bot - commands mirror core Telegram bot functionality using the same API.
"""
import logging
import asyncio
from typing import Optional

import discord
from discord.ext import commands

from .config import DISCORD_BOT_TOKEN, API_URL, COMMAND_PREFIX
from .api_client import api_get

logger = logging.getLogger("diplomacy.discord_bot.bot")

# Max length for a single Discord message (safety)
DISCORD_MAX_MESSAGE = 2000


def _truncate(text: str, max_len: int = DISCORD_MAX_MESSAGE - 50) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def create_bot() -> commands.Bot:
    """Create and configure the Discord bot (prefix commands)."""
    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)

    @bot.event
    async def on_ready() -> None:
        logger.info(f"Discord bot logged in as {bot.user} (id={bot.user.id})")
        logger.info(f"API URL: {API_URL}")

    @bot.command(name="games", help="List all games (from API)")
    async def cmd_games(ctx: commands.Context) -> None:
        try:
            data = await asyncio.to_thread(api_get, "/games")
            games_list = data.get("games", [])
            if not games_list:
                await ctx.send("No games found.")
                return
            lines = []
            for g in games_list[:15]:
                gid = g.get("game_id") or g.get("id")
                turn = g.get("current_turn", 0)
                year = g.get("current_year", 1901)
                season = g.get("current_season", "Spring")
                phase = g.get("current_phase", "Movement")
                players = g.get("player_count", len(g.get("players", [])))
                lines.append(f"**{gid}** — {season} {year} {phase} — {players} players")
            msg = "**Games**\n" + "\n".join(lines)
            if len(games_list) > 15:
                msg += f"\n_... and {len(games_list) - 15} more_"
            await ctx.send(_truncate(msg))
        except Exception as e:
            logger.exception("games command failed")
            await ctx.send(f"Failed to fetch games: {e}")

    @bot.command(name="status", help="Game status: !status <game_id>")
    async def cmd_status(ctx: commands.Context, game_id: Optional[str] = None) -> None:
        if not game_id:
            await ctx.send("Usage: !status <game_id>")
            return
        try:
            data = await asyncio.to_thread(api_get, f"/games/{game_id}/state")
            game_id_val = data.get("game_id", game_id)
            phase_code = data.get("phase_code", "")
            year = data.get("current_year", 1901)
            season = data.get("current_season", "Spring")
            phase = data.get("current_phase", "Movement")
            powers = data.get("powers", {})
            lines = [f"**Game {game_id_val}** — {phase_code} ({season} {year} {phase})"]
            for power, pstate in list(powers.items())[:7]:
                eliminated = " (eliminated)" if pstate.get("is_eliminated") else ""
                sc = len(pstate.get("controlled_supply_centers", []))
                units = pstate.get("units", [])
                lines.append(f"• {power}: {len(units)} units, {sc} SCs{eliminated}")
            await ctx.send(_truncate("\n".join(lines)))
        except Exception as e:
            logger.exception("status command failed")
            await ctx.send(f"Failed to fetch status: {e}")

    @bot.command(name="bothelp", help="Show Diplomacy Discord bot commands")
    async def cmd_bothelp(ctx: commands.Context) -> None:
        prefix = COMMAND_PREFIX
        msg = (
            f"**Diplomacy Discord Bot**\n"
            f"Commands (prefix `{prefix}`):\n"
            f"• `{prefix}games` — List all games\n"
            f"• `{prefix}status <game_id>` — Game status and powers\n"
            f"• `{prefix}bothelp` — This message\n"
            f"Backend: {API_URL}"
        )
        await ctx.send(_truncate(msg))

    return bot


def run_discord_bot() -> None:
    """Run the Discord bot (blocking). Call only if DISCORD_BOT_TOKEN is set."""
    if not DISCORD_BOT_TOKEN:
        logger.info("DIPLOMACY_DISCORD_BOT_TOKEN not set; Discord bot disabled.")
        return
    bot = create_bot()
    try:
        bot.run(DISCORD_BOT_TOKEN, log_handler=None)
    except discord.LoginFailure as e:
        logger.error(f"Discord bot login failed: {e}")
        raise
    except Exception as e:
        logger.exception(f"Discord bot error: {e}")
        raise
