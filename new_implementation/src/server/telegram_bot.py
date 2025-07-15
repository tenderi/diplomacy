"""
Telegram Diplomacy Bot - Initial scaffold

This bot will handle registration, order submission, and notifications for Diplomacy games.
"""
import logging
import os
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont # type: ignore
import asyncio
from fastapi import FastAPI, Request
import uvicorn
from pydantic import BaseModel
from telegram.ext import Application
from typing import Optional
from engine.map import Map

logging.basicConfig(level=logging.INFO)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
API_URL = os.environ.get("DIPLOMACY_API_URL", "http://localhost:8000")

# --- Helper functions for API calls ---
def api_post(endpoint: str, json: dict) -> dict:
    resp = requests.post(f"{API_URL}{endpoint}", json=json)
    resp.raise_for_status()
    return resp.json()

def api_get(endpoint: str) -> dict:
    resp = requests.get(f"{API_URL}{endpoint}")
    resp.raise_for_status()
    return resp.json()

# --- Telegram Bot Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    await update.message.reply_text(
        "Welcome to Diplomacy! Use /register to register, /join to join a game, /games to list games."
    )

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Registration failed: No user context.")
        return
    user_id = str(user.id)
    full_name = getattr(user, 'full_name', None)
    try:
        api_post("/users/persistent_register", {"telegram_id": user_id, "full_name": full_name})
        await update.message.reply_text(
            f"Registered as {full_name or 'Unknown'} (id: {user_id}). Use /join <game_id> <power> to join a game."
        )
    except Exception as e:
        await update.message.reply_text(f"Registration error: {e}")

async def games(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not update.message:
        return
    user_id = str(user.id)
    try:
        # List all games the user is in
        user_games = api_get(f"/users/{user_id}/games")
        games_list = user_games.get("games", [])
        if not games_list:
            await update.message.reply_text("You are not in any games. Use /join <game_id> <power> to join.")
            return
        lines = ["Your games:"]
        for g in games_list:
            lines.append(f"Game {g['game_id']} as {g['power']}")
        await update.message.reply_text("\n".join(lines))
    except Exception as e:
        await update.message.reply_text(f"Error retrieving games: {e}")

async def join(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Game joining failed: No user context.")
        return
    user_id = str(user.id)
    args = context.args if context.args is not None else []
    if len(args) < 2:
        await update.message.reply_text("Usage: /join <game_id> <power>")
        return
    game_id, power = args[0], args[1].upper()
    try:
        result = api_post(f"/games/{game_id}/join", {"telegram_id": user_id, "game_id": int(game_id), "power": power})
        if result.get("status") == "ok":
            await update.message.reply_text(f"You have joined game {game_id} as {power}.")
        elif result.get("status") == "already_joined":
            await update.message.reply_text(f"You are already in game {game_id} as {power}.")
        else:
            await update.message.reply_text(f"Join failed: {result}")
    except Exception as e:
        await update.message.reply_text(f"Failed to join game: {e}")

async def quit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Quit failed: No user context.")
        return
    user_id = str(user.id)
    args = context.args if context.args is not None else []
    if len(args) < 1:
        await update.message.reply_text("Usage: /quit <game_id>")
        return
    game_id = args[0]
    try:
        result = api_post(f"/games/{game_id}/quit", {"telegram_id": user_id, "game_id": int(game_id)})
        if result.get("status") == "ok":
            await update.message.reply_text(f"You have quit game {game_id}.")
        elif result.get("status") == "not_in_game":
            await update.message.reply_text(f"You are not in game {game_id}.")
        else:
            await update.message.reply_text(f"Quit failed: {result}")
    except Exception as e:
        await update.message.reply_text(f"Failed to quit game: {e}")

# Update order-related commands to accept game_id as an argument
async def orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Order submission failed: No user context.")
        return
    user_id = str(user.id)
    args = context.args if context.args is not None else []
    if len(args) < 2:
        await update.message.reply_text("Usage: /orders <game_id> <order1>; <order2>; ...")
        return
    game_id = args[0]
    order_text = " ".join(args[1:])
    try:
        user_games = api_get(f"/users/{user_id}/games")
        power = None
        games_list = user_games.get("games", [])
        for g in games_list:
            if str(g["game_id"]) == str(game_id):
                power = g["power"]
                break
        if not power:
            await update.message.reply_text(f"You are not in game {game_id}.")
            return
        orders = [o.strip() for o in order_text.split(";") if o.strip()]
        if not orders:
            await update.message.reply_text("No orders found in your message.")
            return
        result = api_post("/games/set_orders", {"game_id": game_id, "power": power, "orders": orders})
        results = result.get("results", [])
        if not results:
            await update.message.reply_text("No orders were processed.")
            return
        response_lines = []
        for r in results:
            if r["success"]:
                response_lines.append(f"✅ {r['order']}")
            else:
                response_lines.append(f"❌ {r['order']}\n   Error: {r['error']}")
        await update.message.reply_text("Order results:\n" + "\n".join(response_lines))
    except Exception as e:
        await update.message.reply_text(f"Order error: {e}")

async def myorders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Could not retrieve orders: No user context.")
        return
    user_id = str(user.id)
    try:
        session = api_get(f"/users/{user_id}")
        game_id = session["game_id"]
        power = session["power"]
        result = api_get(f"/games/{game_id}/orders/{power}")
        orders = result.get("orders", [])
        if not orders:
            await update.message.reply_text("You have not submitted any orders for this turn.")
        else:
            await update.message.reply_text(f"Your current orders:\n" + "\n".join(orders))
    except Exception as e:
        await update.message.reply_text(f"Error retrieving orders: {e}")

async def clearorders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Could not clear orders: No user context.")
        return
    user_id = str(user.id)
    try:
        session = api_get(f"/users/{user_id}")
        game_id = session["game_id"]
        power = session["power"]
        api_post(f"/games/{game_id}/orders/{power}/clear", {})
        await update.message.reply_text("Your orders for this turn have been cleared.")
    except Exception as e:
        await update.message.reply_text(f"Error clearing orders: {e}")

async def orderhistory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Could not retrieve order history: No user context.")
        return
    user_id = str(user.id)
    try:
        session = api_get(f"/users/{user_id}")
        game_id = session["game_id"]
        result = api_get(f"/games/{game_id}/orders/history")
        history = result.get("order_history", {})
        if not history:
            await update.message.reply_text("No order history found for this game.")
            return
        lines = [f"Order history for game {game_id}:"]
        for turn in sorted(history.keys(), key=lambda x: int(x)):
            lines.append(f"\nTurn {turn}:")
            for power, orders in history[turn].items():
                lines.append(f"  {power}:")
                for order in orders:
                    lines.append(f"    {order}")
        await update.message.reply_text("\n".join(lines))
    except Exception as e:
        await update.message.reply_text(f"Error retrieving order history: {e}")

async def message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Message failed: No user context.")
        return
    user_id = str(user.id)
    args = context.args if context.args is not None else []
    if len(args) < 3:
        await update.message.reply_text("Usage: /message <game_id> <power> <text>")
        return
    game_id, power = args[0], args[1].upper()
    text = " ".join(args[2:])
    try:
        result = api_post(f"/games/{game_id}/message", {"telegram_id": user_id, "recipient_power": power, "text": text})
        if result.get("status") == "ok":
            await update.message.reply_text(f"Message sent to {power} in game {game_id}.")
        else:
            await update.message.reply_text(f"Message failed: {result}")
    except Exception as e:
        await update.message.reply_text(f"Message error: {e}")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Broadcast failed: No user context.")
        return
    user_id = str(user.id)
    args = context.args if context.args is not None else []
    if len(args) < 2:
        await update.message.reply_text("Usage: /broadcast <game_id> <text>")
        return
    game_id = args[0]
    text = " ".join(args[1:])
    try:
        result = api_post(f"/games/{game_id}/broadcast", {"telegram_id": user_id, "text": text})
        if result.get("status") == "ok":
            await update.message.reply_text(f"Broadcast sent in game {game_id}.")
        else:
            await update.message.reply_text(f"Broadcast failed: {result}")
    except Exception as e:
        await update.message.reply_text(f"Broadcast error: {e}")

async def messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Could not retrieve messages: No user context.")
        return
    user_id = str(user.id)
    args = context.args if context.args is not None else []
    if len(args) < 1:
        await update.message.reply_text("Usage: /messages <game_id>")
        return
    game_id = args[0]
    try:
        result = api_get(f"/games/{game_id}/messages?telegram_id={user_id}")
        messages = result.get("messages", [])
        if not messages:
            await update.message.reply_text("No messages found for this game.")
            return
        lines = [f"Messages for game {game_id}:"]
        for m in messages:
            ts = m["timestamp"]
            sender = m["sender_user_id"]
            recipient = m["recipient_power"] or "ALL"
            lines.append(f"[{ts}] To {recipient}: {m['text']}")
        await update.message.reply_text("\n".join(lines))
    except Exception as e:
        await update.message.reply_text(f"Error retrieving messages: {e}")

async def map_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Map command failed: No user context.")
        return
    user_id = str(user.id)
    args = context.args if context.args is not None else []
    if len(args) < 1:
        await update.message.reply_text("Usage: /map <game_id>")
        return
    game_id = args[0]
    try:
        # Fetch game state from API or server
        game_state = api_get(f"/games/{game_id}/state")
        if not game_state or "units" not in game_state:
            await update.message.reply_text(f"Game {game_id} not found or no units present.")
            return
        units = game_state["units"]  # {power: ["A PAR", "F LON", ...]}
        svg_path = "new_implementation/maps/standard.svg"
        try:
            img_bytes = Map.render_board_png(svg_path, units)
        except Exception as e:
            await update.message.reply_text(f"Error rendering map: {e}")
            return
        await update.message.reply_photo(photo=BytesIO(img_bytes), caption=f"Board for game {game_id}")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

# --- FastAPI notification endpoint ---
fastapi_app = FastAPI()

class NotifyRequest(BaseModel):
    telegram_id: int
    message: str

@fastapi_app.post("/notify")
async def notify(req: NotifyRequest):
    try:
        # Send message using the running Telegram bot application
        if not hasattr(notify, "telegram_app"):
            return {"status": "error", "detail": "Bot not initialized"}
        telegram_app: Application = notify.telegram_app
        await telegram_app.bot.send_message(chat_id=req.telegram_id, text=req.message)
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

# --- Main entrypoint: run both bot and FastAPI ---
def main():
    if not TELEGRAM_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN environment variable not set.")
        return
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("register", register))
    app.add_handler(CommandHandler("join", join))
    app.add_handler(CommandHandler("games", games))
    app.add_handler(CommandHandler("quit", quit))
    app.add_handler(CommandHandler("orders", orders))
    app.add_handler(CommandHandler("myorders", myorders))
    app.add_handler(CommandHandler("clearorders", clearorders))
    app.add_handler(CommandHandler("orderhistory", orderhistory))
    app.add_handler(CommandHandler("message", message))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("messages", messages))
    app.add_handler(CommandHandler("map", map_command))

    # Attach the running app to the notify endpoint for access
    notify.telegram_app = app

    async def run_all():
        uvicorn_server = uvicorn.Server(uvicorn.Config(fastapi_app, host="0.0.0.0", port=8081, log_level="info"))
        api_task = asyncio.to_thread(uvicorn_server.run)
        polling = app.run_polling()
        awaitables = [a for a in [polling, api_task] if a is not None]
        if awaitables:
            await asyncio.gather(*awaitables)

    asyncio.run(run_all())

if __name__ == "__main__":
    main()
