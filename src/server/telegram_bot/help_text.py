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
- **Every order starts with its unit** (W7, decided strict 2026-09-24). The old
  server's alternates -- unit-less (``PAR H``), verb-first (``RETREAT F IRI -
  MAO``, ``REMOVE F LIV``) and multi-hop convoy routes (``A LON - NTH - BEL``)
  -- are rejected on purpose: one canonical form, which is all the bot's
  interactive order menus and the web client ever send. They are listed in
  ``REJECTED_ORDER_FORMS``, shown to players as "not accepted", and the test
  checks each one really fails to parse.

If you add an example here, run ``pytest tests/test_bot_help_text.py``.
"""

# The AGPL (section 13) requires offering the source to everyone who uses the
# program over a network, which includes the bot's players. /help shows it; a
# modified deployment must point this at its own source.
SOURCE_URL = "https://github.com/tenderi/diplomacy"

# W7: forms the old server accepted and this one rejects, each shown next to
# its canonical spelling. tests/test_bot_help_text.py asserts every one of
# these still fails to parse (and every other example still parses).
REJECTED_ORDER_FORMS = (
    "PAR H",
    "RETREAT F IRI - MAO",
    "REMOVE F LIV",
    "A LON - NTH - BEL",
)

# The shared "how do I write an order" block. Imported by /rules, /help, and
# the demo-game help so the three cannot disagree again.
ORDER_FORMAT_NOTES = """*📝 Order Format:*
• Provinces are 3-letter codes: `BER`, `KIE`, `MAO`, and `STP/SC` for a coast
• Units are always `A` (army) or `F` (fleet), never spelled out
• Verbs work short or long: `H`/`HOLD`, `S`/`SUPPORT`, `C`/`CONVOY`, `R`/`RETREAT`, `D`/`DISBAND`, `BUILD`
• Mixing the two is fine: `A BER H` ✅ and `A BER HOLD` ✅ are the same order
• Case doesn't matter, and common aliases work (`baltic` for `BAL`)
• Always start with the unit. Not accepted: `PAR H` (write `A PAR H`), `RETREAT F IRI - MAO` (write `F IRI R MAO`), `REMOVE F LIV` (write `D F LIV`), `A LON - NTH - BEL` (write `A LON - BEL VIA CONVOY`)
• Not sure of a code? Use `/orderall` or `/selectunit` — they only offer legal orders"""

RULES_TEXT = f"""
📜 *Diplomacy Rules & Order Syntax*

*🎯 Basic Rules:*
• 7 powers compete for control of Europe
• Each turn has 3 phases: Movement, Retreat, Builds
• Control supply centers to build units
• Eliminate other powers to win

*📝 Order Types:*
• *Move:* `A PAR - BUR` (Army Paris moves to Burgundy)
• *Hold:* `A PAR H` (Army Paris holds position)
• *Support:* `A MAR S A PAR - BUR` (Army Marseilles supports Paris → Burgundy)
• *Convoy:* `F NTH C A LON - BEL` (Fleet North Sea convoys London → Belgium)
• *Move via Convoy:* `A LON - BEL VIA CONVOY` (Army moves via convoy chain)

*🏗️ Build Phase Orders:*
• *Build:* `BUILD A PAR` (Build an army in Paris)
• *Build on a coast:* `BUILD F STP/SC` (Naming the coast is required)
• *Disband:* `D A MUN` (Disband the army in Munich)
• *Waive:* `WAIVE` (Skip an available build)

*↩️ Retreat Phase Orders:*
• *Retreat:* `A MUN R SIL` (Retreat the dislodged army in Munich to Silesia)
• *Disband:* `D A MUN` (Disband instead of retreating)

{ORDER_FORMAT_NOTES}

*🔄 Game Phases:*
• *Movement* (Spring/Autumn): Submit movement, support, convoy orders
• *Retreat*: Retreat dislodged units to adjacent provinces, or disband
• *Builds*: Build, disband, or waive based on supply center control

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
• *Attack:* `A VIE - TRI`
• *Defend:* `A VIE H`
• *Support Attack:* `A BUD S A VIE - TRI`
• *Support Defense:* `A BUD S A VIE`
• *Convoy Attack:* `F NTH C A LON - BEL` + `A LON - BEL VIA CONVOY`

*🗺️ Province codes:* the first three letters of the name, almost always —
Berlin `BER`, Munich `MUN`, Marseilles `MAR`. The exceptions worth knowing are
the seas: North Sea `NTH`, English Channel `ENG`, Mid-Atlantic `MAO`,
Tyrrhenian `TYS`, Gulf of Lyon `LYO`.
"""

HELP_TEXT = f"""
🏛️ *Diplomacy Bot*

*🎮 The easy way: buttons*
• 🎮 *My games* -- open a game's menu: order all units or one, your orders, map, messages, deadline, ready
• 🎲 *Find a game* -- join an open game, queue for a new one, or try a solo demo
• Notifications ("turn processed", "deadline soon") have an *Enter orders* button

Commands act on your *current game* -- the one you last opened, named, or got
a notification about -- so the game id is only needed to switch games.

*📝 Orders*
• `/orderall` - Order every unit, one by one, then submit them together
• `/selectunit` - Order a single unit
• `/orders <orders>` - Type orders, separated by `;`. Each adds to the ones you sent before; a new order for a unit replaces its old one
• `/myorders`, `/clearorders`, `/orderhistory`

*🎮 Games*
• `/games` - Your games; `/game [id]` - a game's menu (and make it current)
• `/status`, `/viewmap`, `/players`
• `/findgame` - Open games, the queue, the demo; `/join <id> [power] [password]`
• `/leavequeue` - Leave the queue for a new game; `/quit <id>` - leave a game

*💬 Talking*
• `/messages` - Messages in your game
• `/message <power> <text>`, `/broadcast <text>` - Or use 💬 Messages in the game menu and just type

*👥 Playing with your Telegram group*
• Add me to the group and send `/newgame` there; everyone joins with the button I post
• After every turn the group sees two maps (the orders, then the result), deadline reminders and broadcasts
• Orders and private messages always come here, to this private chat
• Only a group's members can see or join its games

*⏰ Pace*
• `/notready` / `/ready` - Ask the table to wait before a turn auto-processes, or stop waiting
• `/deadline <id>` - Show it; `/deadline <id> <hours|clear>` - set or remove it. To put a change to a vote, use ⏰ Deadline in the game menu
• `/deadline <id> schedule mon,wed,fri 16:00 [Europe/Helsinki]` - A deadline every week at those times (`schedule off` stops it)
• `/draw` / `/nodraw` - Vote to end the game as a draw
• Game creator: `/autoprocess <id> on|off`, `/dummy <id> <power> [off]`, and ⚙️ Process turn now in the game menu

*🔧 Other*
• `/feedback <text>` - Report a problem or an idea to the maintainer (your current game is attached)
• `/queue` - Orders/messages waiting for the game server, if it is unreachable
• `/rules`, `/examples` - Order syntax reference
• `/cancel` - Stop writing a message or password

{ORDER_FORMAT_NOTES}

📖 New player guide: https://diplomacy-docs.xn--jalluthti-02a.fi/NEW_USER_GUIDE/
📜 Free software under the GNU AGPL v3 or later, based on diplomacy/diplomacy. Source code: {SOURCE_URL}
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
