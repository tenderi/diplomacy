"""
Admin commands for the Telegram bot.
"""
import logging
import os
import subprocess
import asyncio
import glob

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from .api_client import api_post
from .maps import send_demo_map
from .utils import escape_markdown, safe_markdown_path

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
        await send_demo_map(update, context, game_id)

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
            "• `A Berlin - Kiel` (Army move)\n"
            "• `A Munich - Bohemia` (Army move)\n"
            "• `F Kiel - Denmark` (Fleet move)\n"
            "• `A Berlin H` (Hold)\n"
            "• `A Berlin S A Munich - Kiel` (Support)\n"
            "• `F Kiel C A Berlin - Denmark` (Convoy)\n\n"
            "*📝 Order Format:*\n"
            "• Use abbreviations: `A`, `F`, `H`, `S`, `C`\n"
            "• Or full names: `ARMY`, `FLEET`, `HOLD`, `SUPPORT`, `CONVOY`\n"
            "• **Don't mix:** `A Berlin H` ✅ or `ARMY Berlin HOLD` ✅\n\n"
            "*Interactive Features:*\n"
            "• Use `/selectunit` for guided order selection\n"
            "• Use `/processturn {game_id}` to advance the game\n"
            "• Use `/viewmap {game_id}` to see current state"
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


async def run_automated_demo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Run the perfect demo game script and show results"""
    try:
        # Validate update object
        if not update:
            logger.error("run_automated_demo: update is None")
            return

        if not update.message and not update.callback_query:
            logger.error("run_automated_demo: no message or callback_query in update")
            return

        # Helper function to safely send messages with Markdown error handling
        async def safe_reply_text(text: str, parse_mode: str = None):
            try:
                if update.callback_query:
                    await update.callback_query.message.reply_text(text, parse_mode=parse_mode)
                else:
                    await update.message.reply_text(text, parse_mode=parse_mode)
            except Exception as e:
                error_str = str(e)
                # If it's a Markdown parsing error, retry without parse_mode
                if "parse entities" in error_str.lower() or "can't find end" in error_str.lower():
                    logger.warning(f"Markdown parsing error, retrying as plain text: {e}")
                    try:
                        if update.callback_query:
                            await update.callback_query.message.reply_text(text, parse_mode=None)
                        else:
                            await update.message.reply_text(text, parse_mode=None)
                    except Exception as e2:
                        logger.error(f"Error sending message even as plain text: {e2}")
                        # Log the problematic message for debugging
                        logger.debug(f"Problematic message content (first 500 chars): {text[:500]}")
                else:
                    logger.error(f"Error sending message: {e}")
                    # Log the problematic message for debugging
                    logger.debug(f"Problematic message content (first 500 chars): {text[:500]}")

        async def safe_reply_photo(photo_file, caption: str = None, parse_mode: str = None):
            try:
                if update.callback_query:
                    await update.callback_query.message.reply_photo(photo=photo_file, caption=caption, parse_mode=parse_mode)
                else:
                    await update.message.reply_photo(photo=photo_file, caption=caption, parse_mode=parse_mode)
            except Exception as e:
                logger.error(f"Error sending photo: {e}")

        # Get the project root by going up from the current file (telegram_bot/admin.py)
        # admin.py is in src/server/telegram_bot/, so go up 3 levels to get project root
        current_file_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file_dir)))

        # Try multiple possible locations for the demo script
        # 1. examples/demo_perfect_game.py (for local development)
        # 2. demo_perfect_game.py in project root (for deployment)
        possible_paths = [
            os.path.join(project_root, "examples", "demo_perfect_game.py"),
            os.path.join(project_root, "demo_perfect_game.py")
        ]
        
        script_path = None
        for path in possible_paths:
            if os.path.exists(path):
                script_path = path
                break
        
        # Check if the script exists
        if not script_path:
            error_msg = (
                f"❌ Demo script not found. Checked locations:\n"
                f"  • {possible_paths[0]}\n"
                f"  • {possible_paths[1]}"
            )
            if update.callback_query:
                await update.callback_query.edit_message_text(error_msg)
            else:
                await update.message.reply_text(error_msg)
            return

        # Set up environment with correct PYTHONPATH
        env = os.environ.copy()
        src_dir = os.path.join(project_root, "src")
        if os.path.exists(src_dir):
            env["PYTHONPATH"] = f"{src_dir}:{env.get('PYTHONPATH', '')}"
        else:
            env["PYTHONPATH"] = f"{project_root}:{env.get('PYTHONPATH', '')}"

        # Run the demo script with proper environment
        result = subprocess.run(
            ["/usr/bin/python3", script_path],
            capture_output=True,
            text=True,
            cwd=project_root,
            env=env
        )

        if result.returncode == 0:
            # Success - post generated maps in order
            # Try multiple possible locations for test_maps directory
            possible_maps_dirs = [
                os.path.join(project_root, "test_maps"),  # Project root
                os.path.join(project_root, "examples", "test_maps"),  # Examples subdirectory
                os.path.join(os.path.dirname(script_path), "test_maps") if script_path else None,  # Same dir as script
            ]
            
            maps_dir = None
            map_files = []
            
            for maps_dir_candidate in possible_maps_dirs:
                if maps_dir_candidate and os.path.exists(maps_dir_candidate):
                    # Get all generated map files in chronological order
                    map_files = sorted(glob.glob(os.path.join(maps_dir_candidate, "perfect_demo_*.png")))
                    if map_files:
                        maps_dir = maps_dir_candidate
                        break
            
            # If still no maps found, try to find any test_maps directory
            if not map_files:
                for root, dirs, files in os.walk(project_root):
                    if 'test_maps' in dirs:
                        test_maps_path = os.path.join(root, 'test_maps')
                        map_files = sorted(glob.glob(os.path.join(test_maps_path, "perfect_demo_*.png")))
                        if map_files:
                            maps_dir = test_maps_path
                            break
                    if map_files:
                        break

            if map_files:
                # Send initial message
                await safe_reply_text("🎬 *Perfect Demo Game Complete!*\n\n📊 Posting generated maps in chronological order...", parse_mode='Markdown')

                # Post each map with description
                for i, map_file in enumerate(map_files, 1):
                    try:
                        # Extract phase info from filename
                        filename = os.path.basename(map_file)
                        phase_info = filename.replace("perfect_demo_", "").replace(".png", "").replace("_", " ").title()

                        # Create caption
                        caption = f"🗺️ *Map {i}/{len(map_files)}*\n📅 {phase_info}\n\n🎮 Perfect Diplomacy Demo Game"

                        # Send the map
                        with open(map_file, 'rb') as f:
                            await safe_reply_photo(f, caption=caption, parse_mode='Markdown')

                        # Small delay between maps
                        await asyncio.sleep(1)

                    except Exception as e:
                        logger.error(f"Error posting map {map_file}: {e}")
                        continue

                # Send completion message
                completion_msg = (
                    f"✅ *Perfect Demo Complete!*\n\n"
                    f"📊 Generated {len(map_files)} maps showing the complete game progression\n"
                    f"🎮 Hardcoded perfect scenarios demonstrating all mechanics\n"
                    f"📈 Shows 2-1 battles, support cuts, convoys, retreats, and builds"
                )

                await safe_reply_text(completion_msg, parse_mode='Markdown')
            else:
                # No maps generated, show text summary with diagnostic info
                # Determine the relative path for the help message
                script_rel_path = os.path.relpath(script_path, project_root) if script_path else "demo_perfect_game.py"
                
                # Check if maps_dir exists but is empty
                maps_dir_exists = maps_dir and os.path.exists(maps_dir) if maps_dir else False
                maps_dir_info = f"Maps directory: {maps_dir}" if maps_dir else "Maps directory: not found"
                
                # Check stdout/stderr for errors
                stderr_output = result.stderr[-500:] if result.stderr else ""  # Last 500 chars
                stdout_output = result.stdout[-500:] if result.stdout else ""  # Last 500 chars
                has_errors = "Could not generate" in stderr_output or "Could not generate" in stdout_output or "Error" in stderr_output
                
                # Escape paths and dynamic content for Markdown
                escaped_maps_dir = escape_markdown(maps_dir) if maps_dir else "not found"
                escaped_project_root = escape_markdown(project_root)
                escaped_script_path = escape_markdown(script_rel_path)
                escaped_maps_path = safe_markdown_path(maps_dir or os.path.join(project_root, 'test_maps'))
                
                success_msg = (
                    "🎬 *Perfect Demo Game Complete!*\n\n"
                    "✅ The demo game ran successfully, but no maps were generated\\.\n\n"
                    f"📊 *Diagnostics:*\n"
                    f"  • Maps directory: {escaped_maps_dir}\n"
                    f"  • Project root: {escaped_project_root}\n"
                    f"  • Script path: {escaped_script_path}\n"
                )
                
                if has_errors:
                    success_msg += "\n⚠️ *Errors detected in output \\- check logs for details\\.*\n"
                
                success_msg += (
                    "\n💡 *To run the demo yourself:*\n"
                    "```bash\n"
                    f"cd {escape_markdown(project_root)}\n"
                    f"/usr/bin/python3 {escaped_script_path}\n"
                    "```\n\n"
                    f"📁 *Maps will be saved to:* {escaped_maps_path}"
                )

                await safe_reply_text(success_msg, parse_mode='Markdown')
        else:
            # Error occurred - escape error messages for Markdown
            escaped_stderr = escape_markdown(result.stderr[:500]) if result.stderr else "No error output"
            escaped_stdout = escape_markdown(result.stdout[:500]) if result.stdout else "No output"
            
            error_msg = (
                f"❌ *Demo script failed*\n\n"
                f"**Error:** {escaped_stderr}\n\n"
                f"**Output:** {escaped_stdout}"
            )

            await safe_reply_text(error_msg, parse_mode='Markdown')

    except Exception as e:
        error_msg = f"❌ Error running perfect demo: {escape_markdown(str(e))}"
        logger.error(f"run_automated_demo exception: {e}")
        try:
            if update and (update.callback_query or update.message):
                if update.callback_query:
                    await update.callback_query.edit_message_text(error_msg)
                else:
                    await update.message.reply_text(error_msg)
        except Exception as reply_error:
            logger.error(f"Failed to send error message: {reply_error}")


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

