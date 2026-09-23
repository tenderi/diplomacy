"""
Admin commands for the Telegram bot.
"""
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from .api_client import api_post
from .help_text import DEMO_EXAMPLE_ORDERS, ORDER_FORMAT_NOTES
from .maps import send_game_map

logger = logging.getLogger("diplomacy.telegram_bot.admin")


async def start_demo_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start a demo game where the user plays as Germany with all units in starting positions"""
    try:
        user_id = str(update.effective_user.id)
        user_name = update.effective_user.full_name or "Demo Player"

        # Register the user first (required for joining games)
        try:
            api_post("/users/persistent_register", {
                "telegram_id": user_id,
                "full_name": user_name
            })
        except Exception as e:
            # User might already be registered, continue
            logger.info(f"User registration note: {e}")

        # Create a demo game
        game_resp = api_post("/games/create", {"map_name": "demo"})
        game_id = game_resp["game_id"]

        # Add the user as Germany
        api_post(f"/games/{game_id}/join", {
            "telegram_id": user_id,
            "game_id": int(game_id),
            "power": "GERMANY"
        })

        # Add AI players for other powers (they won't submit orders)
        other_powers = ["AUSTRIA", "ENGLAND", "FRANCE", "ITALY", "RUSSIA", "TURKEY"]
        for power in other_powers:
            ai_telegram_id = f"ai_{power.lower()}"
            # Register AI player
            try:
                api_post("/users/persistent_register", {
                    "telegram_id": ai_telegram_id,
                    "full_name": f"AI {power}"
                })
            except Exception as e:
                # AI player might already be registered, continue
                logger.info(f"AI player registration note: {e}")

            # Join the game
            api_post(f"/games/{game_id}/join", {
                "telegram_id": ai_telegram_id,
                "game_id": int(game_id),
                "power": power
            })

        # Generate the map with starting positions
        await send_game_map(update, context, game_id)

        # Show demo game controls
        keyboard = [
            [InlineKeyboardButton("📋 Submit Orders", callback_data=f"demo_orders_{game_id}")],
            [InlineKeyboardButton("🗺️ View Map", callback_data=f"view_map_{game_id}")],
            [InlineKeyboardButton("ℹ️ Demo Help", callback_data=f"demo_help_{game_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        demo_text = (
            f"🎮 *Demo Game Started!* (ID: {game_id})\n\n"
            "🇩🇪 *You are Germany* - Make your moves!\n"
            "🤖 Other powers are AI-controlled (they won't move)\n\n"
            "💡 *Available Commands:*\n"
            "📋 Submit orders for Germany\n"
            "🗺️ View current map state\n"
            "ℹ️ Get help with demo mode\n\n"
            "*Example Orders:*\n"
            f"{DEMO_EXAMPLE_ORDERS}\n\n"
            f"{ORDER_FORMAT_NOTES}\n\n"
            "*Interactive Features:*\n"
            "• Use `/selectunit` for guided order selection\n"
            f"• Use `/processturn {game_id}` to advance the game\n"
            f"• Use `/viewmap {game_id}` to see current state"
        )

        if update.callback_query:
            await update.callback_query.edit_message_text(
                demo_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                demo_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )

    except Exception as e:
        error_msg = f"❌ Error starting demo game: {str(e)}"
        if update.callback_query:
            await update.callback_query.edit_message_text(error_msg)
        else:
            await update.message.reply_text(error_msg)


async def debug_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Debug command to show user information"""
    if not update.message:
        return

    user = update.effective_user
    user_id = str(user.id)
    user_id_int = user.id

    debug_text = (
        f"🔍 *Debug Information*\n\n"
        f"👤 User ID (str): `{user_id}`\n"
        f"👤 User ID (int): `{user_id_int}`\n"
        f"📝 User ID Type: `{type(user_id)}`\n"
        f"🔢 Is 8019538?: `{user_id == '8019538'}`\n"
        f"📛 Username: `{user.username or 'None'}`\n"
        f"📛 Full Name: `{user.full_name or 'None'}`\n\n"
        f"⚙️ Admin Access: {'✅ YES' if user_id == '8019538' else '❌ NO'}"
    )

    await update.message.reply_text(debug_text, parse_mode='Markdown')

