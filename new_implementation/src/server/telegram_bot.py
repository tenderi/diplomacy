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
    await update.message.reply_text(
        f"Registered as {getattr(user, 'full_name', 'Unknown')} (id: {getattr(user, 'id', 'Unknown')}). Use /join to join a game."
    )

async def games(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    # List all games (not implemented in API, placeholder)
    await update.message.reply_text("Game listing not yet implemented.")

async def join(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Game joining failed: No user context.")
        return
    user_id = str(user.id)
    # For now, always create a new game for demo
    try:
        result = api_post("/games/create", {"map_name": "standard"})
        game_id = str(result["game_id"])
        # Assign first available power (for demo, always FRANCE)
        power = "FRANCE"
        api_post("/games/add_player", {"game_id": game_id, "power": power})
        api_post("/users/register", {"telegram_id": user_id, "game_id": game_id, "power": power})
        await update.message.reply_text(f"You have joined game {game_id} as {power}.")
    except Exception as e:
        await update.message.reply_text(f"Failed to join game: {e}")

async def orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Order submission failed: No user context.")
        return
    user_id = str(user.id)
    try:
        # Get user session
        session = api_get(f"/users/{user_id}")
        game_id = session["game_id"]
        power = session["power"]
        order_text = update.message.text or ""
        # Remove "/orders" prefix
        if order_text.lower().startswith("/orders"):
            order_text = order_text[7:].strip()
        # Split by semicolon for multi-order
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
    app.add_handler(CommandHandler("orders", orders))
    app.add_handler(CommandHandler("myorders", myorders))
    app.add_handler(CommandHandler("clearorders", clearorders))
    app.add_handler(CommandHandler("orderhistory", orderhistory))

    # Attach the running app to the notify endpoint for access
    notify.telegram_app = app

    async def run_all():
        # Run both the Telegram bot and FastAPI app concurrently
        bot_task = asyncio.create_task(app.run_polling())
        uvicorn_server = uvicorn.Server(uvicorn.Config(fastapi_app, host="0.0.0.0", port=8081, log_level="info"))
        api_task = asyncio.create_task(asyncio.to_thread(uvicorn_server.run))
        await asyncio.gather(bot_task, api_task)

    asyncio.run(run_all())

if __name__ == "__main__":
    main()
