"""
Order management commands for the Telegram bot.

The bot is a thin client over the HTTP API -- it never imports the engine or
the renderer. Interactive order selection (``/selectunit`` and the callback
chain it kicks off) is driven entirely by ``GET
/games/{id}/legal_orders/{power}`` (see ``src/server/legal_orders.py``),
which is phase-aware (MOVEMENT / RETREAT / ADJUSTMENT) and emits canonical,
ready-to-submit order strings -- so nothing here re-derives adjacency,
coasts, or order grammar locally.
"""
from typing import Any, Awaitable, Callable, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from .api_client import api_post, api_get
from .game_context import GameContextError, fetch_user_games, resolve_game_and_power

Sender = Callable[..., Awaitable[None]]


# ---------------------------------------------------------------------------
# order-string helpers (shared by the interactive selection flow)
# ---------------------------------------------------------------------------

_VERB_EMOJI = {"H": "🛑", "-": "➡️", "S": "🤝", "C": "🚢", "R": "↩️", "D": "❌"}


def _order_verb(order_str: str) -> str:
    """The verb token of a unit-first order string (index 2), or ``""``.

    Unit-first orders (hold/move/support/convoy/retreat/disband) all have
    the shape ``"{kind} {location} {verb} ..."`` -- see the "PR2 facts" in
    ``docs/specs/fix_plan.md``: build/waive orders are verb-first
    (``"BUILD F BRE"``, ``"WAIVE"``) and never appear in a per-unit
    ``orders_by_unit`` bucket, only in the flat ``orders`` list, so this
    helper is never applied to them.
    """
    parts = order_str.split()
    return parts[2] if len(parts) > 2 else ""


def _order_label(order_str: str) -> str:
    """A short, emoji-prefixed button label for a canonical order string."""
    if order_str == "WAIVE":
        label = "⏭️ Waive build"
    elif order_str.startswith("BUILD "):
        label = f"🏗️ {order_str}"
    else:
        emoji = _VERB_EMOJI.get(_order_verb(order_str), "")
        label = f"{emoji} {order_str}".strip()
    return label if len(label) <= 60 else label[:57] + "..."


async def _present_order_choices(
    send: Sender,
    context: ContextTypes.DEFAULT_TYPE,
    game_id: str,
    header: str,
    order_strings: list[str],
) -> None:
    """Cache ``order_strings`` for this game and show one button per order.

    Each button's ``callback_data`` is ``ord|{game_id}|{idx}`` -- never the
    order text itself. Embedding full order strings (as the pre-rewrite
    scheme did) overflows Telegram's 64-byte ``callback_data`` cap on
    coasted/support/convoy orders; an index into a cache does not, no matter
    how long the underlying order string is. ``send`` is any
    ``async (text, reply_markup=None) -> None`` callable, so this works from
    both a plain message reply and a callback-query edit.
    """
    if not order_strings:
        await send(f"{header}\n\n(no options available)")
        return
    context.user_data.setdefault("pending_orders", {})[str(game_id)] = list(order_strings)
    keyboard = [
        [InlineKeyboardButton(_order_label(s), callback_data=f"ord|{game_id}|{i}")]
        for i, s in enumerate(order_strings)
    ]
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data=f"cancelunit|{game_id}")])
    await send(header, reply_markup=InlineKeyboardMarkup(keyboard))


def resolve_pending_order(context: ContextTypes.DEFAULT_TYPE, game_id: str, idx: int) -> Optional[str]:
    """Resolve an ``ord|{game_id}|{idx}`` callback back to its order text.

    Returns ``None`` if the cache is missing (bot restarted, ``user_data``
    cleared) or ``idx`` is stale/out of range -- callers must treat that as
    "selection expired", not crash.
    """
    cached = context.user_data.get("pending_orders", {}).get(str(game_id))
    if cached is None or not (0 <= idx < len(cached)):
        return None
    return cached[idx]


async def order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Submit one or more orders, matching docs/TELEGRAM_BOT_COMMANDS.md's
    ``/order [game_id] <order>; <order>; ...``: an optional leading game id,
    then semicolon-separated orders (same split rule as ``/orders``).

    A leading token is treated as the game id only when it's purely
    numeric -- no order string in this grammar starts with a digit (unit
    orders start with the unit letter ``A``/``F``; build/waive/disband
    orders are verb-first: ``BUILD``, ``WAIVE``, ``D``), so this can't
    misparse a legitimate order as carrying a game id.

    Game id omitted: works only when the caller is in exactly one game
    (``resolve_game_and_power`` raises ``GameContextError`` with a
    disambiguation prompt otherwise) -- the "auto-detect your game" behavior
    this command originally had.
    """
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Order submission failed: No user context.")
        return
    user_id = str(user.id)
    args = context.args if context.args is not None else []

    if len(args) < 1:
        await update.message.reply_text(
            "Usage: /order [game_id] <order>; <order>; ...\n\n"
            "Examples:\n"
            "/order A BER - SIL\n"
            "/order F KIE - DEN; A MUN S A BER - SIL\n"
            "/order 2 A BER - SIL\n\n"
            "The game id is only needed if you're in more than one game."
        )
        return

    game_id_arg: Optional[str] = None
    order_args = args
    if args[0].isdigit():
        game_id_arg = args[0]
        order_args = args[1:]

    order_text = " ".join(order_args)
    order_list = [o.strip() for o in order_text.split(";") if o.strip()]
    if not order_list:
        await update.message.reply_text("No orders found in your message.")
        return

    try:
        game_id, power = resolve_game_and_power(user_id, game_id_arg)
    except GameContextError as e:
        await update.message.reply_text(e.message)
        return
    except Exception as e:
        await update.message.reply_text(f"Order error: {e}")
        return

    try:
        result = api_post("/games/set_orders", {
            "game_id": game_id,
            "power": power,
            "orders": order_list,
            "telegram_id": user_id
        })
    except Exception as e:
        await update.message.reply_text(f"Order error: {e}")
        return

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


async def orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Submit orders for a specific game."""
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
    game_id_arg = args[0]
    order_text = " ".join(args[1:])

    try:
        game_id, power = resolve_game_and_power(user_id, game_id_arg)
    except GameContextError as e:
        await update.message.reply_text(e.message)
        return
    except Exception as e:
        await update.message.reply_text(f"Order error: {e}")
        return

    order_list = [o.strip() for o in order_text.split(";") if o.strip()]
    if not order_list:
        await update.message.reply_text("No orders found in your message.")
        return

    try:
        result = api_post(
            "/games/set_orders",
            {"game_id": game_id, "power": power, "orders": order_list, "telegram_id": user_id},
        )
    except Exception as e:
        await update.message.reply_text(f"Order error: {e}")
        return

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


async def myorders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """View current orders for the user's active game."""
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Could not retrieve orders: No user context.")
        return
    user_id = str(user.id)
    args = context.args if context.args is not None else []
    game_id_arg = args[0] if args else None

    try:
        game_id, power = resolve_game_and_power(user_id, game_id_arg)
    except GameContextError as e:
        await update.message.reply_text(e.message)
        return
    except Exception as e:
        await update.message.reply_text(f"Error retrieving orders: {e}")
        return

    try:
        result = api_get(f"/games/{game_id}/orders/{power}", telegram_id=user_id)
    except Exception as e:
        await update.message.reply_text(f"Error retrieving orders: {e}")
        return

    order_list = result.get("orders", [])
    if not order_list:
        await update.message.reply_text("You have not submitted any orders for this turn.")
    else:
        await update.message.reply_text("Your current orders:\n" + "\n".join(order_list))


async def clearorders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clear orders for the user's active game."""
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Could not clear orders: No user context.")
        return
    user_id = str(user.id)
    args = context.args if context.args is not None else []
    game_id_arg = args[0] if args else None

    try:
        game_id, power = resolve_game_and_power(user_id, game_id_arg)
    except GameContextError as e:
        await update.message.reply_text(e.message)
        return
    except Exception as e:
        await update.message.reply_text(f"Error clearing orders: {e}")
        return

    try:
        # telegram_id must be present so api_post injects bot_secret into the
        # body -- the clear route requires it for auth. Without this the
        # request 401s (the bug this rewrite fixes).
        api_post(f"/games/{game_id}/orders/{power}/clear", {"telegram_id": user_id})
    except Exception as e:
        await update.message.reply_text(f"Error clearing orders: {e}")
        return

    await update.message.reply_text("Your orders for this turn have been cleared.")


async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /clear command - alias for /clearorders."""
    await clearorders(update, context)


async def orderhistory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """View order history for the user's active game."""
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Could not retrieve order history: No user context.")
        return
    user_id = str(user.id)
    args = context.args if context.args is not None else []
    game_id_arg = args[0] if args else None

    try:
        game_id, _power = resolve_game_and_power(user_id, game_id_arg)
    except GameContextError as e:
        await update.message.reply_text(e.message)
        return
    except Exception as e:
        await update.message.reply_text(f"Error retrieving order history: {e}")
        return

    try:
        result = api_get(f"/games/{game_id}/orders/history")
    except Exception as e:
        await update.message.reply_text(f"Error retrieving order history: {e}")
        return

    history = result.get("order_history", {})
    if not history:
        await update.message.reply_text("No order history found for this game.")
        return
    lines = [f"Order history for game {game_id}:"]
    for turn in sorted(history.keys(), key=lambda x: int(x)):
        lines.append(f"\nTurn {turn}:")
        for power, power_orders in history[turn].items():
            lines.append(f"  {power}:")
            for o in power_orders:
                lines.append(f"    {o}")
    await update.message.reply_text("\n".join(lines))


async def processturn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process the current turn/phase for a game.

    Checks ``GET /games/{id}/orders_status`` first (the same endpoint
    ``/status`` already uses). ``POST /process_turn`` defaults to
    ``require_all=false``, so if any active power hasn't submitted orders
    yet, processing now would silently turn their units into holds -- this
    asks for explicit confirmation via an inline button instead of doing
    that unannounced.
    """
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Process turn failed: No user context.")
        return
    user_id = str(user.id)
    args = context.args if context.args is not None else []

    if len(args) < 1:
        await update.message.reply_text(
            "Usage: /processturn <game_id>\n\n"
            "This command advances the current phase and processes all submitted orders.\n"
            "Use this after all players have submitted their orders for the turn."
        )
        return

    try:
        game_id, _power = resolve_game_and_power(user_id, args[0])
    except GameContextError as e:
        await update.message.reply_text(e.message)
        return
    except Exception as e:
        await update.message.reply_text(f"Process turn error: {e}")
        return

    try:
        orders_status = api_get(f"/games/{game_id}/orders_status", telegram_id=user_id)
    except Exception:
        orders_status = None

    missing = orders_status.get("missing", []) if orders_status else []
    if missing:
        keyboard = [
            [InlineKeyboardButton("✅ Process anyway", callback_data=f"ptforce|{game_id}")],
            [InlineKeyboardButton("❌ Cancel", callback_data=f"ptcancel|{game_id}")],
        ]
        await update.message.reply_text(
            f"⚠️ *Not everyone has submitted orders yet for Game {game_id}.*\n\n"
            f"⏳ Still waiting on: {', '.join(missing)}\n\n"
            f"Processing now will treat their units as holding. Continue?",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown',
        )
        return

    await run_process_turn(update.message.reply_text, game_id)


async def run_process_turn(send: Sender, game_id: str) -> None:
    """Adjudicate ``game_id``'s current phase (``POST /process_turn``) and
    report a short outcome summary.

    ``send`` is any ``async (text, reply_markup=None, parse_mode=None) ->
    None`` callable, so this works from both a plain message reply
    (``processturn``) and a callback-query edit (the "Process anyway"
    confirmation button in ``app.py``).

    The summary is built from ``dislodged``/``contested`` on ``GET
    /games/{id}/state`` -- those are the only per-turn outcome fields that
    exist on this branch. A richer per-order summary (who succeeded, who
    bounced, why) needs the JSON resolution endpoint that's landing on a
    separate branch; until then this is deliberately coarse.
    """
    try:
        result = api_post(f"/games/{game_id}/process_turn", {})
    except Exception as e:
        await send(f"❌ Process turn error: {e}")
        return

    if result.get("status") != "ok":
        error_msg = result.get("detail", "Unknown error")
        await send(f"❌ Failed to process turn: {error_msg}")
        return

    try:
        game_state = api_get(f"/games/{game_id}/state")
    except Exception:
        game_state = None

    if not game_state:
        await send("✅ Turn processed successfully!")
        return

    phase = game_state.get("phase", "Unknown")
    status_value = game_state.get("status", "IN_PROGRESS")
    dislodged = game_state.get("dislodged", [])
    contested = game_state.get("contested", [])

    lines = ["✅ *Turn Processed!*", f"📊 New phase: {phase}"]

    if dislodged:
        lines.append("\n💥 *Dislodged:*")
        for d in dislodged:
            unit = d.get("unit", {})
            kind = unit.get("kind", "?")
            loc = unit.get("location", "?")
            power = unit.get("power", "?")
            retreats = d.get("retreats") or []
            fate = f"can retreat to {', '.join(retreats)}" if retreats else "no retreats available (disbanded)"
            lines.append(f"  • {power} {kind} {loc} -- {fate}")

    if contested:
        lines.append("\n⚔️ *Standoffs:* " + ", ".join(contested))

    if status_value == "COMPLETED":
        winners = game_state.get("winners") or []
        winners_text = ", ".join(winners) if winners else "no one"
        lines.append(f"\n🏁 *Game Complete!* Winners: {winners_text}")
        lines.append(f"\nView the final map with /viewmap {game_id}")
    else:
        lines.append(
            f"\n🎮 Submit orders for the next phase, or /viewmap {game_id} to see the board."
        )

    await send("\n".join(lines), parse_mode='Markdown')


async def viewmap(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """View the current map for a specific game"""
    from .maps import send_game_map  # Import here to avoid circular dependency

    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("View map failed: No user context.")
        return
    user_id = str(user.id)
    args = context.args if context.args is not None else []

    if len(args) < 1:
        await update.message.reply_text(
            "Usage: /viewmap <game_id>\n\n"
            "This command shows the current map state for the specified game."
        )
        return

    try:
        game_id, _power = resolve_game_and_power(user_id, args[0])
    except GameContextError as e:
        await update.message.reply_text(e.message)
        return
    except Exception as e:
        await update.message.reply_text(f"View map error: {e}")
        return

    try:
        await send_game_map(update, context, game_id)
    except Exception as e:
        await update.message.reply_text(f"View map error: {e}")


async def selectunit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show phase-appropriate order choices for the user's units.

    Branches on ``phase_type`` from ``GET /games/{id}/legal_orders/{power}``:
    MOVEMENT and RETREAT both show one button per unit (existing units, or
    dislodged units respectively) leading into ``show_possible_moves``;
    ADJUSTMENT has no "unit to select" step -- build/waive candidates aren't
    tied to an existing unit, and disband candidates are exactly the
    player's units, one order each -- so it presents the flat order list
    directly.
    """
    user = update.effective_user
    if not user:
        if update.message:
            await update.message.reply_text("Select unit failed: No user context.")
        elif update.callback_query:
            await update.callback_query.edit_message_text("Select unit failed: No user context.")
        return
    user_id = str(user.id)
    args = context.args if context.args is not None else []
    game_id_arg = args[0] if args else None

    async def reply_or_edit(
        text: str, reply_markup: Optional[InlineKeyboardMarkup] = None, parse_mode: str = 'Markdown'
    ) -> None:
        """Helper function to handle both message and callback query contexts"""
        if update.message:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        elif update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode=parse_mode)

    try:
        game_id, power = resolve_game_and_power(user_id, game_id_arg)
    except GameContextError as e:
        await reply_or_edit(e.message)
        return
    except Exception as e:
        await reply_or_edit(f"Select unit error: {e}")
        return

    try:
        data = api_get(f"/games/{game_id}/legal_orders/{power}")
    except Exception as e:
        await reply_or_edit(f"❌ Could not retrieve legal orders for game {game_id}: {e}")
        return

    phase_type = data.get("phase_type", "MOVEMENT")

    if phase_type == "ADJUSTMENT":
        adjustment = data.get("adjustment", {})
        flat_orders = data.get("orders", [])
        if adjustment.get("action") in (None, "none") or not flat_orders:
            await reply_or_edit(
                f"✅ No adjustment actions needed for {power} in game {game_id} "
                f"(delta: {adjustment.get('delta', 0)})."
            )
            return
        header = (
            f"🏗️ *Adjustment for {power}* (Game {game_id})\n\n"
            f"Delta: {adjustment.get('delta')} | Action: {adjustment.get('action')} "
            f"| Slots: {adjustment.get('slots')}\n\nChoose an order:"
        )
        await _present_order_choices(reply_or_edit, context, game_id, header, flat_orders)
        return

    units = data.get("units", [])
    if not units:
        label = "retreat" if phase_type == "RETREAT" else "orders"
        await reply_or_edit(f"❌ No units require {label} for {power} in game {game_id}.")
        return

    keyboard = []
    for u in units:
        key = f"{u['kind']} {u['location']}"
        emoji = "🛡️" if u["kind"] == "A" else "🚢"
        keyboard.append([InlineKeyboardButton(f"{emoji} {key}", callback_data=f"selunit|{game_id}|{key}")])
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data=f"cancelunit|{game_id}")])

    phase_header = {
        "MOVEMENT": "Select a unit for orders",
        "RETREAT": "Select a dislodged unit to retreat/disband",
    }.get(phase_type, "Select a unit")

    await reply_or_edit(
        f"🎯 *{phase_header}*\n\n"
        f"📊 Game: {game_id} | Power: {power} | Phase: {data.get('phase')}\n\n"
        f"🛡️ Army | 🚢 Fleet",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def show_possible_moves(
    query: Any, context: ContextTypes.DEFAULT_TYPE, game_id: str, unit_key: str
) -> None:
    """Show non-convoy legal orders for one unit, plus a convoy sub-menu if any exist.

    ``unit_key`` is exactly an ``orders_by_unit`` key, ``"{kind} {location}"``
    (e.g. ``"F STP/SC"``). Convoy orders are split into a separate
    "Convoy options" step (``show_convoy_options``) instead of listed inline:
    an open-water fleet's bucket can contain a full cross product of
    origin/destination convoy pairs, which would otherwise dominate the menu.
    """
    async def send(text: str, reply_markup: Optional[InlineKeyboardMarkup] = None) -> None:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    try:
        user_id = str(query.from_user.id)
        _, power = resolve_game_and_power(user_id, game_id)
    except GameContextError as e:
        await send(e.message)
        return
    except Exception as e:
        await send(f"❌ Could not resolve your power in game {game_id}: {e}")
        return

    try:
        data = api_get(f"/games/{game_id}/legal_orders/{power}")
    except Exception as e:
        await send(f"❌ Could not retrieve legal orders: {e}")
        return

    bucket = data.get("orders_by_unit", {}).get(unit_key, [])
    if not bucket:
        await send(f"❌ No legal orders found for {unit_key} in game {game_id}.")
        return

    convoy_orders = [o for o in bucket if _order_verb(o) == "C"]
    direct_orders = [o for o in bucket if _order_verb(o) != "C"]

    context.user_data.setdefault("pending_orders", {})[str(game_id)] = list(direct_orders)
    keyboard = [
        [InlineKeyboardButton(_order_label(s), callback_data=f"ord|{game_id}|{i}")]
        for i, s in enumerate(direct_orders)
    ]
    if convoy_orders:
        keyboard.append(
            [InlineKeyboardButton("🚢 Convoy options", callback_data=f"cvopt|{game_id}|{unit_key}")]
        )
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data=f"cancelunit|{game_id}")])

    emoji = "🛡️" if unit_key.startswith("A ") else "🚢"
    await send(
        f"🎯 *Orders for {emoji} {unit_key}*\n\n📊 Game: {game_id} | Power: {power}\n\nChoose an order:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def show_convoy_options(
    query: Any, context: ContextTypes.DEFAULT_TYPE, game_id: str, unit_key: str
) -> None:
    """Show the distinct armies a fleet can convoy (grouped by origin province).

    A fleet's convoy bucket already contains one fully-formed order string
    per (origin, destination) pair; this groups them by origin so the user
    picks an army first, then a destination (``show_convoy_destinations``),
    instead of facing every pair in one long list. The intermediate
    callback (``cvorig|{game_id}|{unit_key}|{origin}``) carries only short
    province codes, never order text.
    """
    async def send(text: str, reply_markup: Optional[InlineKeyboardMarkup] = None) -> None:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    try:
        user_id = str(query.from_user.id)
        _, power = resolve_game_and_power(user_id, game_id)
    except GameContextError as e:
        await send(e.message)
        return
    except Exception as e:
        await send(f"❌ Could not resolve your power in game {game_id}: {e}")
        return

    try:
        data = api_get(f"/games/{game_id}/legal_orders/{power}")
    except Exception as e:
        await send(f"❌ Could not retrieve legal orders: {e}")
        return

    bucket = data.get("orders_by_unit", {}).get(unit_key, [])
    convoy_orders = [o for o in bucket if _order_verb(o) == "C"]
    if not convoy_orders:
        await send(f"❌ No convoy options found for {unit_key} in game {game_id}.")
        return

    # "F NTH C A LON - BEL".split() -> ["F","NTH","C","A","LON","-","BEL"]; origin province is index 4.
    origins = sorted({o.split()[4] for o in convoy_orders if len(o.split()) > 4})
    keyboard = [
        [InlineKeyboardButton(f"🪖 {origin}", callback_data=f"cvorig|{game_id}|{unit_key}|{origin}")]
        for origin in origins
    ]
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data=f"cancelunit|{game_id}")])

    await send(
        f"🚢 *Convoy via {unit_key}: choose the army to move*\n\n📊 Game: {game_id}",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def show_convoy_destinations(
    query: Any, context: ContextTypes.DEFAULT_TYPE, game_id: str, unit_key: str, origin: str
) -> None:
    """Show destination choices for convoying the army standing at ``origin``."""
    async def send(text: str, reply_markup: Optional[InlineKeyboardMarkup] = None) -> None:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    try:
        user_id = str(query.from_user.id)
        _, power = resolve_game_and_power(user_id, game_id)
    except GameContextError as e:
        await send(e.message)
        return
    except Exception as e:
        await send(f"❌ Could not resolve your power in game {game_id}: {e}")
        return

    try:
        data = api_get(f"/games/{game_id}/legal_orders/{power}")
    except Exception as e:
        await send(f"❌ Could not retrieve legal orders: {e}")
        return

    bucket = data.get("orders_by_unit", {}).get(unit_key, [])
    dest_orders = [
        o for o in bucket
        if _order_verb(o) == "C" and len(o.split()) > 4 and o.split()[4] == origin
    ]
    if not dest_orders:
        await send(f"❌ No convoy destinations found for {unit_key} → {origin}.")
        return

    await _present_order_choices(
        send, context, game_id, f"🚢 *Convoy {origin} via {unit_key}*\n\nChoose destination:", dest_orders
    )


async def submit_interactive_order(query: Any, game_id: str, order_text: str) -> None:
    """Submit an order string chosen through the interactive selection flow.

    ``order_text`` is always a canonical string that came straight from
    ``legal_orders`` (or, for the ``ord|`` callback path, was cached
    verbatim from it) -- it is posted as-is. The pre-rewrite version ran
    user-typed strings through a local province-name normalizer that would
    have mangled verb-first strings like ``WAIVE``/``BUILD F BRE``/``D A
    PAR``; that normalizer is gone (v2.7.24) and the server's single order
    grammar (``engine.orders.parser``) now resolves aliases for every order,
    typed or generated, via ``MapData.aliases``.
    """
    try:
        user_id = str(query.from_user.id)
        _, power = resolve_game_and_power(user_id, game_id)
    except GameContextError as e:
        await query.edit_message_text(e.message)
        return
    except Exception as e:
        await query.edit_message_text(f"❌ Could not resolve your power in game {game_id}: {e}")
        return

    try:
        result = api_post("/games/set_orders", {
            "game_id": game_id,
            "power": power,
            "orders": [order_text],
            "telegram_id": user_id
        })
    except Exception as e:
        await query.edit_message_text(f"❌ Error submitting order: {e}")
        return

    results = result.get("results", [])
    if results and results[0]["success"]:
        await query.edit_message_text(
            f"✅ *Order Submitted Successfully!*\n\n"
            f"📋 Order: `{order_text}`\n"
            f"🎮 Game: {game_id}\n"
            f"👤 Power: {power}\n\n"
            f"💡 *Next Steps:*\n"
            f"• Submit more orders with /selectunit\n"
            f"• Process turn with /processturn {game_id}\n"
            f"• View map with /viewmap {game_id}\n"
            f"• View orders with /myorders {game_id}\n"
            f"• Clear orders with /clearorders {game_id}",
            parse_mode='Markdown'
        )
    else:
        error_msg = results[0]["error"] if results else "Unknown error"
        await query.edit_message_text(
            f"❌ *Order Failed*\n\n"
            f"📋 Order: `{order_text}`\n"
            f"❌ Error: {error_msg}\n\n"
            f"💡 Try selecting a different order with /selectunit",
            parse_mode='Markdown'
        )


async def show_my_orders_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show orders menu for user's games"""
    try:
        user_id = str(update.effective_user.id)
        user_games = fetch_user_games(user_id)

        # Handle different response types safely
        if not user_games or not isinstance(user_games, list) or len(user_games) == 0:
            # Create helpful keyboard for users not in games
            keyboard = [
                [InlineKeyboardButton("🎲 Browse Available Games", callback_data="show_games_list")],
                [InlineKeyboardButton("⏳ Join Waiting List", callback_data="join_waiting_list")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "📋 *No Active Games*\n\n"
                "🎮 You're not currently in any games!\n\n"
                "💡 *Get started:*\n"
                "🎲 Browse games and pick one to join\n"
                "⏳ Join the waiting list for auto-matching",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            return

        keyboard = []
        # Safely handle list slicing
        games_to_show = user_games[:10] if len(user_games) > 10 else user_games
        for game in games_to_show:
            if isinstance(game, dict):
                game_id = game.get('game_id', 'Unknown')
                power = game.get('power', 'Unknown')
                state = game.get('status', 'Unknown')
                # Add more context to button text
                button_text = f"📋 Game {game_id} ({power}) - {state}"
                keyboard.append([InlineKeyboardButton(button_text, callback_data=f"orders_menu_{game_id}_{power}")])

        if not keyboard:
            # Fallback if games exist but are malformed
            keyboard = [[InlineKeyboardButton("🎲 Browse Games Instead", callback_data="show_games_list")]]
            await update.message.reply_text(
                "📋 *Games Data Issue*\n\n"
                "🔧 Your games data seems corrupted. Try browsing available games instead.",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            return

        reply_markup = InlineKeyboardMarkup(keyboard)
        if update.callback_query:
            await update.callback_query.edit_message_text(
                f"📋 *Select game to manage orders:* ({len(games_to_show)} active)",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                f"📋 *Select game to manage orders:* ({len(games_to_show)} active)",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )

    except Exception as e:
        # More helpful error message with recovery options
        keyboard = [
            [InlineKeyboardButton("🔄 Try Again", callback_data="retry_orders_menu")],
            [InlineKeyboardButton("🎲 Browse Games", callback_data="show_games_list")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if update.callback_query:
            await update.callback_query.edit_message_text(
                f"⚠️ *Temporary Issue*\n\n"
                f"🔧 Unable to load your games right now.\n"
                f"This usually means the server is starting up.\n\n"
                f"💡 *Try:*\n"
                f"• Wait a moment and try again\n"
                f"• Browse available games directly\n"
                f"• Return to main menu\n\n"
                f"*Technical details:* {str(e)[:100]}",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                f"⚠️ *Temporary Issue*\n\n"
                f"🔧 Unable to load your games right now.\n"
                f"This usually means the server is starting up.\n\n"
                f"💡 *Try:*\n"
                f"• Wait a moment and try again\n"
                f"• Browse available games directly\n"
                f"• Return to main menu\n\n"
                f"*Technical details:* {str(e)[:100]}",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
