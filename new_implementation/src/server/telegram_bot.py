"""
Telegram Diplomacy Bot - Initial scaffold

This bot will handle registration, order submission, and notifications for Diplomacy games.
"""
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
import logging
import os
from src.engine.game import Game
from src.engine.order import OrderParser
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont # type: ignore

logging.basicConfig(level=logging.INFO)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

# In-memory game state for demo (replace with DB-backed in production)
games: dict[str, Game] = {}
user_to_power: dict[str, tuple[str, str]] = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text( # type: ignore
        "Welcome to Diplomacy! Use /register to join a game."
    )

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat = update.effective_chat
    if update.message and user:
        await update.message.reply_text(
            f"Registered as {getattr(user, 'full_name', 'Unknown')} (id: {getattr(user, 'id', 'Unknown')}). Use /join to join a game."
        )
    elif chat:
        await chat.send_message("Registration failed: No user context.")

async def join(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat = update.effective_chat
    if not (update.message and user):
        if chat:
            await chat.send_message("Game joining failed: No user context.")
        return
    user_id = str(user.id)
    # For demo: one global game, assign next available power
    game_id = "default"
    if game_id not in games:
        games[game_id] = Game(map_name="mini_variant")
    game = games[game_id]
    # Find an available power
    taken_powers = {p for _, p in user_to_power.values() if _ == game_id}
    available_powers = [p for p in ["RED", "BLUE", "GREEN", "YELLOW", "BLACK", "WHITE", "PURPLE"] if p not in taken_powers]
    if not available_powers:
        await update.message.reply_text("No available powers in this game.")
        return
    assigned_power = available_powers[0]
    game.add_player(assigned_power)
    user_to_power[user_id] = (game_id, assigned_power)
    await update.message.reply_text(f"You have joined the game as {assigned_power}.")

async def order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat = update.effective_chat
    if update.message and user:
        order_text = update.message.text or ""
        order_text = order_text.strip()
        user_id = str(user.id)
        # Find the game and power for this user
        mapping = user_to_power.get(user_id)
        if not mapping:
            if update.message:
                await update.message.reply_text("You are not registered in any game. Use /register and /join.")
            elif chat:
                await chat.send_message("You are not registered in any game. Use /register and /join.")
            return
        game_id, power_name = mapping
        game = games.get(game_id)
        if not game:
            if update.message:
                await update.message.reply_text("Game not found. Please re-join.")
            elif chat:
                await chat.send_message("Game not found. Please re-join.")
            return
        # Parse and validate the order
        try:
            # Prepend power name if not present
            if not order_text.startswith(power_name):
                full_order = f"{power_name} {order_text}"
            else:
                full_order = order_text
            order_obj = OrderParser.parse(full_order)
            valid, msg = OrderParser.validate(order_obj, game.get_state())
            if not valid:
                if update.message:
                    await update.message.reply_text(f"Invalid order: {msg}")
                elif chat:
                    await chat.send_message(f"Invalid order: {msg}")
                return
            # Set the order for this power
            game.set_orders(power_name, [order_text])
            if update.message:
                await update.message.reply_text(f"Order accepted: {order_text}")
            elif chat:
                await chat.send_message(f"Order accepted: {order_text}")
        except Exception as e:
            if update.message:
                await update.message.reply_text(f"Order parsing error: {e}")
            elif chat:
                await chat.send_message(f"Order parsing error: {e}")
    elif chat:
        await chat.send_message("Order submission failed: No user context.")

async def board(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat = update.effective_chat
    user_id = str(user.id) if user else None
    mapping = user_to_power.get(user_id) if user_id else None
    if not mapping:
        if update.message:
            await update.message.reply_text("You are not registered in any game. Use /register and /join.")
        elif chat:
            await chat.send_message("You are not registered in any game. Use /register and /join.")
        return
    game_id, _ = mapping
    game = games.get(game_id)
    if not game:
        if update.message:
            await update.message.reply_text("Game not found. Please re-join.")
        elif chat:
            await chat.send_message("Game not found. Please re-join.")
        return
    # --- Text visualization ---
    board_text = "Current Board State:\n"
    for power, p in game.powers.items():
        board_text += f"{power}: {', '.join(sorted(p.units))}\n"
    if update.message:
        await update.message.reply_text(board_text)
    elif chat:
        await chat.send_message(board_text)
    # --- Image visualization ---
    # Simple grid image: each province as a box, units as colored circles with power initials
    width, height = 600, 400
    img = Image.new("RGB", (width, height), color="white") # type: ignore
    draw = ImageDraw.Draw(img) # type: ignore
    font = ImageFont.load_default() # type: ignore
    # For demo: lay out units in a grid
    all_units = [(power, unit) for power, p in game.powers.items() for unit in p.units]
    cols = 6
    cell_w, cell_h = width // cols, 50
    for idx, (power, unit) in enumerate(all_units):
        col = idx % cols
        row = idx // cols
        x = col * cell_w + cell_w // 2
        y = row * cell_h + cell_h // 2 + 30
        color = {
            "RED": "red", "BLUE": "blue", "GREEN": "green", "YELLOW": "yellow",
            "BLACK": "black", "WHITE": "gray", "PURPLE": "purple"
        }.get(power, "gray")
        draw.ellipse([x-20, y-20, x+20, y+20], fill=color, outline="black") # type: ignore
        draw.text((x-15, y-10), f"{power[0]}\n{unit}", fill="white", font=font) # type: ignore
    # Send image
    bio = BytesIO()
    img.save(bio, format="PNG") # type: ignore
    bio.seek(0)
    if update.message:
        await update.message.reply_photo(photo=bio, caption="Board visualization")
    elif chat:
        await chat.send_photo(photo=bio, caption="Board visualization")

def main():
    if not TELEGRAM_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN environment variable not set.")
        return
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("register", register))
    app.add_handler(CommandHandler("join", join))
    app.add_handler(CommandHandler("board", board))
    # Accept any non-command message as an order for now
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, order))
    app.run_polling()

if __name__ == "__main__":
    main()
