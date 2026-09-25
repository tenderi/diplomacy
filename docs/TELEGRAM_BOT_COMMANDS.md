# Telegram Bot Command Reference

Every command the Diplomacy bot accepts. Arguments in `<>` are required, `[]` optional.

## The button way

Most players never need to type a command after `/start`:

- **🎮 My games** lists your games; tap one to open its **game menu**: the game's status
  (phase, deadline, who has ordered, wait flags, draw vote) and buttons for 📝 Order all
  units, 🎯 One unit, 📋 My orders (with 🗑 Clear and 📜 History), 🗺 Map, 💬 Messages,
  ⏰ Deadline, ✋ Wait for me / ✅ I'm ready (when the game auto-processes), and — for the
  game's creator only — ⚙️ Process turn now. With just one game, 🎮 My games opens its menu
  straight away.
- **🎲 Find a game** lists open games you can join (🔒 = private; tap a power and the bot asks
  for the password, then deletes your message), the queue for the next new game, and a solo
  demo.
- **Notifications** — "turn processed", "deadline in 10 minutes", "you joined", "game is
  full" — carry 📝 Enter orders, 🗺 Map and 🎮 Game menu buttons for that game.
- **💬 Messages** in the game menu shows recent messages and a button per power (and
  📣 Everyone): tap one, then just type your message. `/cancel` stops.

## Your current game

Commands act on your **current game**, so the game id is only needed to switch: it is the
game you last opened in the game menu, named in a command, joined, or tapped a notification
button for. `/game <id>` switches explicitly. With only one game, that game is always
current. (`/deadline`, `/quit`, `/replace`, `/dummy` and `/autoprocess` still take the id
first, because a bare number there would be ambiguous.)

## Getting started

| Command | Description |
|---|---|
| `/start` | Registers you (nothing else to do) and shows the main keyboard: 🎮 My games · 🎲 Find a game · ℹ️ Help. |
| `/help` | Show all available commands. |
| `/rules` | Basic Diplomacy rules and order syntax. |
| `/examples` | Order syntax examples. |
| `/refresh` | Rebuild the keyboard menu if it gets out of sync. |
| `/register` | Still works, but `/start`, joining and queueing register you automatically. |
| `/cancel` | Stop writing a message or password the bot asked for. |
| `/feedback <text>` | Send a report or an idea to the maintainer; your current game and its phase are attached. |

## Account linking

| Command | Description |
|---|---|
| `/link <code>` | Link this Telegram account to a browser account. |

Get the code from the web app: **Link Telegram → Generate link code**, then send
`/link 123456` here. One Telegram account can be linked to one browser account; unlink from
the web app if you need to re-link.

## Game management

| Command | Description |
|---|---|
| `/games` | Your games, as buttons that open each game's menu (⭐ marks the current game). |
| `/game [game_id]` | Open a game's menu, and make it your current game. |
| `/findgame` | Open games you could join, the queue, and the solo demo — the 🎲 Find a game key. |
| `/join <game_id>` | Shows a menu of available powers to join as. |
| `/join <game_id> <power>` | Join directly as a specific power, skipping the menu. |
| `/join <game_id> <power> <password>` | Join a **private** game (🔒 in the game list). Ask the game's creator for the password. The bot deletes your message afterwards so the password doesn't stay in the chat. Five wrong guesses lock you out of that game for 15 minutes. |
| `/quit <game_id>` | Leave a game. Your seat is vacated — units and any orders you submitted stay exactly as they are for whoever takes it over — and you can no longer act for that power (or see it under `/games`). |
| `/replace <game_id> <power> [password]` | Take over a vacated power (a private game needs its password). `/join <game_id> <power>` on a vacated seat does the same thing. |
| `/wait` | Join the queue for a new game (the "⏳ Queue for the next new game" button); a game is created automatically once 7 players are waiting, and everyone in the queue is messaged with their assigned power. The queue is stored server-side, so it survives a bot restart. |
| `/leavequeue` | Leave the queue (`/unwait` still works). |
| `/players [game_id]` | List all players and their powers. |
| `/status [game_id]` | Current phase, deadline, who has submitted orders, and the draw-vote tally. |
| `/draw [game_id]` | Vote yes to end the game as a draw. If your vote completes quorum — every surviving power has voted yes — the game ends immediately. |
| `/nodraw [game_id]` | Withdraw a draw vote you previously cast. |
| `/deadline <game_id> <hours>` | Set the order deadline that many hours from now. The turn is processed automatically when it passes (units without orders hold), everyone in the game is told, and a reminder goes out 10 minutes before. The deadline is spent once its phase is processed; only a weekly schedule (below) sets the next one for you. |
| `/deadline <game_id> clear` | Remove the deadline. |
| `/deadline <game_id>` | Show the current deadline and the weekly schedule, if any. |
| `/deadline <game_id> schedule <days> <HH:MM> [timezone]` | A deadline every week at those times, e.g. `schedule mon,wed,fri 16:00 Europe/Helsinki` (days may be names, ranges such as `mon-fri`, or `daily`; separate groups with different times by `;`, e.g. `mon-fri 18:00; sun 12:00`). The timezone is an IANA name and defaults to UTC. Every phase, retreats and builds included, is then due at the next slot at least an hour away, armed when the game fills and after each turn. A one-off `/deadline <game_id> <hours>` still overrides the current phase only. Everyone is told. |
| `/deadline <game_id> schedule off` | Stop the weekly schedule. The current deadline stays; later phases get none unless someone sets one. |
| ⏰ Deadline (game menu) | Propose 12h / 24h / 48h / no deadline to a majority vote, vote ✅/❌ on a pending proposal, or withdraw your own. (`/deadline <game_id> propose <hours\|clear> [vote_hours]`, `vote <yes\|no>` and `withdraw` do the same by typing.) |
| `/autoprocess <game_id> on\|off` | Any player: process each turn the moment every power with something to order has sent an order **for every unit that must act** (to keep a unit still, order it to hold) (civil-disorder powers are never waited on), unless someone is `/notready`. A deadline still applies. Off by default. |
| `/notready [game_id]` | Ask the table to wait before the turn auto-processes ("I'm still negotiating"). Lasts until `/ready` or the end of the phase. Never stops a deadline. |
| `/ready [game_id]` | Lower your wait flag; if everything else is in, the turn is processed at once. |
| `/dummy <game_id> <power> [off]` | Game creator only: leave an empty seat to civil disorder (it holds, disbands when it must, is never waited on and never votes), or add `off` to open it for a player again. For tables of 3–6. |

### The solo demo

🎲 Find a game → 🎮 Solo demo starts a game where you are Germany and the other six powers
are played by the server with simple computer moves. It processes each turn as soon as all
your units have orders.

## Orders

| Command | Description |
|---|---|
| `/orderall [game_id]` | **Order all your units** — the bot shows each unit that must act this phase in turn (or each build/disband slot), you pick from its legal orders, then review the list and submit it in one go. ⬅️ Back and ⏭ Skip on every step; a skipped unit keeps any earlier order, or holds. Same as 📝 Order all units / 📝 Enter orders. |
| `/selectunit [game_id]` | **Order a single unit** — pick a unit, then pick from its legal orders; it is sent at once. |
| `/orders [game_id] <order>; <order>; …` | Type orders. They are **added** to the orders you already sent this phase; a new order for a unit replaces that unit's earlier one. `/order` is the same command. |
| `/myorders [game_id]` | Show your submitted orders for the current phase. |
| `/clearorders [game_id]`, `/clear [game_id]` | Clear your submitted orders so you can resubmit. |
| `/orderhistory [game_id]` | Orders from previous turns, grouped by turn and power. |
| `/processturn [game_id]` | **The game's creator only** (the ⚙️ Process turn now button): adjudicate the current phase now. If some powers haven't submitted, asks for confirmation first (their units would hold). Everyone else's turns end at the deadline, or when all orders are in with auto-process on. |

Separate multiple orders with semicolons. The buttons are the easiest route — they only ever
offer orders that are legal in the current phase, including retreats and builds.

### Order syntax

```
A PAR - BUR            Army Paris moves to Burgundy
F BRE H                Fleet Brest holds
A MAR S A PAR - BUR    Marseilles supports Paris → Burgundy
F BRE S A PAR          Brest supports Paris to hold
F NTH C A LON - BEL    North Sea convoys London → Belgium
A LON - BEL VIA        Move explicitly via convoy
A MUN R TYR            Retreat (retreat phase)
D A PAR                Disband
BUILD A PAR            Build an army
BUILD F STP/SC         Build a fleet, naming the coast
WAIVE                  Waive a build
```

Parsing is case-insensitive and accepts the usual province abbreviations and aliases.

## Messages

| Command | Description |
|---|---|
| `/message [game_id] <power> <text>` | Private message to one power. Or 💬 Messages in the game menu, tap the power, and type. |
| `/broadcast [game_id] <text>` | Message all players. Also posted to the linked channel, if any. |
| `/messages [game_id]` | Broadcasts plus private messages to and from you, each line showing which power sent it. |
| `/queue` | Whether the game server is reachable, and your orders/messages still waiting to be delivered to it, with the time you sent each. |

### When the game server is unreachable

The bot runs on a different machine from the game server. If the link between them is down
when you send orders or a message, the bot replies that it has **queued** the command with
the time you sent it, delivers it automatically once the server is back, and messages you
with the result. Nothing is lost. Two things to know:

- A message is recorded with the time you *wrote* it, and the recipient sees that time.
- Orders that could not be delivered before the turn was processed are **not** applied to
  the next turn; the bot tells you exactly which ones did not make it.

Everything else (maps, status, joining) needs the server and simply reports that it is
unreachable until it returns. Notifications from the server (turn processed, reminders,
messages to you) are held on the server side and arrive when the link is back, prefixed with
the time they were created if they were delayed.

## Maps

| Command | Description |
|---|---|
| `/map [game_id]`, `/viewmap [game_id]` | Current board as a PNG. |
| `/replay <game_id> <turn>` | The map for a past turn. |

## Playing in a Telegram group

A game can belong to a Telegram group. The group then gets two maps after every
processed turn (the orders, drawn on the board they were given on and coloured by
what they did, then the result), deadline reminders, "the game is full" and players' broadcasts, and **only members
of that group can see or join the game** (🎲 Find a game lists it only for them; the
website does not list it). Orders, private messages and the game menu always stay in
your **private chat** with the bot: in a group, the bot refuses those commands and
offers a link to a private chat instead. Buttons in group posts are links that open
that private chat.

Send these **in the group**:

| Command | Description |
|---|---|
| `/newgame` | Create a game for this group. You become its creator. The bot posts a **Join** button that opens a private chat to pick a power. Turns are processed as soon as every order is in (anyone can ask the table to wait). |
| `/linkgroup [game_id]` | Attach one of your existing games to this group. |
| `/unlinkgroup [game_id]` | Detach it again. |
| `/status [game_id]`, `/viewmap [game_id]`, `/players [game_id]` | Public information about a game, answered in the group. |
| `/help` or `/start` | How playing in a group works. |

### Advanced: channel settings

| Command | Description |
|---|---|
| `/channel_info <game_id>` | The linked group or channel and its settings. |
| `/channel_settings <game_id> <setting> <value>` | Change a setting: `auto_post_maps`, `auto_post_broadcasts`, `auto_post_notifications` (`true`/`false`, default `true`) or `notification_level` (`all`/`important`/`none`). |
| `/link_channel <game_id> <chat_id>`, `/unlink_channel <game_id>` | Link a Telegram *channel* (where the bot can't read commands) by its id, e.g. from @userinfobot. For groups, `/linkgroup` is simpler. |

## Admin

| Command | Description |
|---|---|
| `/debug` | Shows your Telegram user id, username and name (what an admin needs to find you). |

## Troubleshooting

| Message | Fix |
|---|---|
| "You are not in game X" | Join it first: 🎲 Find a game, or `/join`. |
| "You're in N games" | Pick one with `/game <id>`, or open it from 🎮 My games; it stays picked. |
| "Order failed" | Check the syntax and that the order type suits the current phase — the order buttons avoid both problems. |
| "Channel not linked" | Run `/link_channel`. |
| Bot doesn't respond | Confirm the bot and API are running, then send `/start`. |

More: [FAQ and setup](LOCAL_DEVELOPMENT.md#troubleshooting).
