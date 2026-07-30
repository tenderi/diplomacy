"""Canonical, parseable help text for the Telegram bot.

Every order string shown to a player lives here, in one module, because the
alternative already failed: the "Order Format" block was copy-pasted into
``ui.py``, ``admin.py`` and ``app.py``, and all three copies drifted into
teaching syntax the engine rejects (Track G1). ``tests/test_bot_help_text.py``
scans every constant below, extracts each backtick-quoted order, and parses it
through the real ``engine.orders.parser`` — so a wrong example fails CI instead
of reaching a new player.

**The rules the examples must obey** (verified against
``engine/orders/parser.py`` and ``engine/map_loader.py``):

- **Provinces are 3-letter codes** — ``BER``, ``KIE``, ``STP/SC``. Full names do
  *not* parse: ``maps/standard.map``'s ``=`` lines register only their
  right-hand-side spellings as aliases, and no full name is among them
  (``aliases['berlin']`` is ``None``). Single-word aliases like ``baltic`` or
  ``burg`` do work; multi-word names such as ``English Channel`` cannot, because
  the grammar tokenizes on whitespace.
- **The unit kind must be ``A`` or ``F``.** ``ARMY``/``FLEET`` are rejected
  outright (``expected unit kind 'A' or 'F'``).
- **Verbs accept both short and long forms**, and mixing them with the short
  unit kind is fine: ``A BER H`` and ``A BER HOLD`` both parse.

If you add an example here, run ``pytest tests/test_bot_help_text.py``.
"""

# The shared "how do I write an order" block. Imported by /rules, /help, and
# the demo-game help so the three cannot disagree again.
ORDER_FORMAT_NOTES = """*📝 Order Format:*
• Provinces are 3-letter codes: `BER`, `KIE`, `MAO`, and `STP/SC` for a coast
• Units are always `A` (army) or `F` (fleet), never spelled out
• Verbs work short or long: `H`/`HOLD`, `S`/`SUPPORT`, `C`/`CONVOY`, `R`/`RETREAT`, `D`/`DISBAND`, `BUILD`
• Mixing the two is fine: `A BER H` ✅ and `A BER HOLD` ✅ are the same order
• Case doesn't matter, and common aliases work (`baltic` for `BAL`)
• Not sure of a code? Use `/selectunit` — it only offers legal orders"""

RULES_TEXT = f"""
📜 *Diplomacy Rules & Order Syntax*

*🎯 Basic Rules:*
• 7 powers compete for control of Europe
• Each turn has 3 phases: Movement, Retreat, Builds
• Control supply centers to build units
• Eliminate other powers to win

*📝 Order Types:*
• **Move:** `A PAR - BUR` (Army Paris moves to Burgundy)
• **Hold:** `A PAR H` (Army Paris holds position)
• **Support:** `A MAR S A PAR - BUR` (Army Marseilles supports Paris → Burgundy)
• **Convoy:** `F NTH C A LON - BEL` (Fleet North Sea convoys London → Belgium)
• **Move via Convoy:** `A LON - BEL VIA CONVOY` (Army moves via convoy chain)

*🏗️ Build Phase Orders:*
• **Build:** `BUILD A PAR` (Build an army in Paris)
• **Build on a coast:** `BUILD F STP/SC` (Naming the coast is required)
• **Disband:** `D A MUN` (Disband the army in Munich)
• **Waive:** `WAIVE` (Skip an available build)

*↩️ Retreat Phase Orders:*
• **Retreat:** `A MUN R SIL` (Retreat the dislodged army in Munich to Silesia)
• **Disband:** `D A MUN` (Disband instead of retreating)

{ORDER_FORMAT_NOTES}

*🔄 Game Phases:*
• **Movement** (Spring/Autumn): Submit movement, support, convoy orders
• **Retreat**: Retreat dislodged units to adjacent provinces, or disband
• **Builds**: Build, disband, or waive based on supply center control

*💡 Tips:*
• Units can't move into occupied provinces (except with support)
• Support can help attacks or defenses
• Convoy chains allow armies to cross water
• Supply centre ownership persists even if units leave
"""

EXAMPLES_TEXT = """
📚 *Order Syntax Examples*

*🎯 Movement Orders:*
• `A VIE - TRI` - Army Vienna moves to Trieste
• `F LON - NTH` - Fleet London moves to the North Sea
• `A BER - KIE` - Army Berlin moves to Kiel

*🛡️ Hold Orders:*
• `A PAR H` - Army Paris holds
• `F LON H` - Fleet London holds

*🤝 Support Orders:*
• `A MAR S A PAR - BUR` - Army Marseilles supports Paris → Burgundy
• `F BRE S F ENG - MAO` - Fleet Brest supports the English Channel → Mid-Atlantic
• `A MUN S A BER` - Army Munich supports Berlin holding

*🚢 Convoy Orders:*
• `F NTH C A LON - BEL` - Fleet North Sea convoys London → Belgium
• `A LON - BEL VIA CONVOY` - Army moves via convoy (needs a convoying fleet)

*🏗️ Build Phase Orders:*
• `BUILD A PAR` - Build an army in Paris (requires an empty home centre)
• `BUILD F BRE` - Build a fleet in Brest
• `BUILD F STP/SC` - Build a fleet on a named coast
• `D A MUN` - Disband the army in Munich (if you have too many units)
• `WAIVE` - Skip an available build

*↩️ Retreat Phase Orders:*
• `A MUN R SIL` - Retreat the dislodged army in Munich to Silesia
• `D A MUN` - Disband instead of retreating

*📝 Multiple Orders:*
Separate multiple orders with semicolons:
• `A PAR - BUR; F BRE - ENG; A MAR H`

*💡 Common Patterns:*
• **Attack:** `A VIE - TRI`
• **Defend:** `A VIE H`
• **Support Attack:** `A BUD S A VIE - TRI`
• **Support Defense:** `A BUD S A VIE`
• **Convoy Attack:** `F NTH C A LON - BEL` + `A LON - BEL VIA CONVOY`

*🗺️ Province codes:* the first three letters of the name, almost always —
Berlin `BER`, Munich `MUN`, Marseilles `MAR`. The exceptions worth knowing are
the seas: North Sea `NTH`, English Channel `ENG`, Mid-Atlantic `MAO`,
Tyrrhenian `TYS`, Gulf of Lyon `LYO`.
"""

HELP_TEXT = f"""
🏛️ *Diplomacy Bot Commands*

*🎯 Getting Started:*
• Register - Register as a player
• My Games - View your current games
• Join Game - Join a specific game
• Join Waiting List - Auto-match with others

*🎮 During Games:*
• My Orders - Submit/view your orders
• View Map - See current game state
• Messages - View/send diplomatic messages

*📝 Text Commands:*
• `/orders <game_id> <orders>` - Submit orders
• `/order <orders>` - Submit orders (auto-detect game)
• `/selectunit` - Interactive unit selection
• `/processturn <game_id>` - Process current turn
• `/viewmap <game_id>` - View game map
• `/message <game_id> <power> <text>` - Send message
• `/broadcast <game_id> <text>` - Message all players
• `/myorders <game_id>` - View your orders
• `/clearorders <game_id>` - Clear your orders
• `/orderhistory <game_id>` - View order history
• `/draw [game_id]` - Vote yes to end the game as a draw
• `/nodraw [game_id]` - Withdraw your draw vote
• `/status [game_id]` - Phase, deadline, and draw-vote tally
• `/rules`, `/examples` - Order syntax reference

*🗺️ Order Types & Examples:*
• `A VIE - TRI` (Army move)
• `F LON - NTH` (Fleet move)
• `A BER H` (Hold)
• `A BER S A MUN - KIE` (Support)
• `F ENG C A LON - BRE` (Convoy)
• `BUILD A PAR` (Build unit - Builds phase only)
• `D A MUN` (Disband unit - Builds/Retreat phase only)
• `WAIVE` (Skip an available build - Builds phase only)
• `A MUN R SIL` (Retreat to Silesia - Retreat phase only)

{ORDER_FORMAT_NOTES}

*🎯 Game Phases:*
• **Movement** (Spring/Autumn) - Submit movement orders
• **Retreat** - Retreat dislodged units, or disband (`D`)
• **Builds** - Build, disband (`D`), or waive (`WAIVE`) based on supply centers

*💡 Tips:*
• Use `/selectunit` for interactive order selection
• Use menu buttons for easier navigation
• Orders are validated in real-time
• Convoy chains are automatically validated
"""

# Germany's opening position, used by the demo game in both `admin.py` (the
# start-demo reply) and `app.py` (the demo_help callback).
DEMO_EXAMPLE_ORDERS = """• `A BER - KIE` (Army move)
• `A MUN - BOH` (Army move)
• `F KIE - DEN` (Fleet move)
• `A BER H` (Hold)
• `A BER S A MUN - KIE` (Support)
• `F KIE C A BER - DEN` (Convoy)"""

DEMO_UNITS = """• `A BER` (Army in Berlin)
• `A MUN` (Army in Munich)
• `F KIE` (Fleet in Kiel)"""
