# Telegram Bot Command Reference

Every command the Diplomacy bot accepts. Arguments in `<>` are required, `[]` optional.
Where `[game_id]` is optional, the bot infers it when you are in exactly one game.

## Getting started

| Command | Description |
|---|---|
| `/start` | Welcome message and the main keyboard menu. |
| `/register` | Register yourself as a user. Required before joining games. |
| `/help` | Show all available commands. |
| `/rules` | Basic Diplomacy rules and order syntax. |
| `/examples` | Order syntax examples. |
| `/refresh` | Rebuild the keyboard menu if it gets out of sync. |

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
| `/games` | List the games you are in, with your power and the current phase. |
| `/join <game_id>` | Join a game. Shows a power-selection menu if several are open. |
| `/quit <game_id>` | Leave a game. Your power becomes available for replacement. |
| `/replace <game_id> <power>` | Take over a vacated power. |
| `/wait` | Join the waiting list; a new game is created automatically once 7 players are waiting. |
| `/players [game_id]` | List all players and their powers. |
| `/status [game_id]` | Current phase, deadline, and who has submitted orders. |

## Orders

| Command | Description |
|---|---|
| `/order [game_id] <order>; <order>; …` | Submit orders. |
| `/orders <game_id> <order>; <order>; …` | Same, but the game ID is required. |
| `/selectunit [game_id]` | **Interactive order entry** — pick a unit, then pick from its legal orders. |
| `/myorders [game_id]` | Show your submitted orders for the current phase. |
| `/clearorders [game_id]`, `/clear [game_id]` | Clear your submitted orders so you can resubmit. |
| `/orderhistory <game_id>` | Orders from previous turns, grouped by turn and power. |
| `/processturn <game_id>` | Adjudicate the current phase and advance. |

Separate multiple orders with semicolons. `/selectunit` is the easiest route — it only ever
offers orders that are legal in the current phase, including retreats and builds.

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
| `/message <game_id> <power> <text>` | Private message to one power. |
| `/broadcast <game_id> <text>` | Message all players. Also posted to the linked channel, if any. |
| `/messages [game_id]` | Broadcasts plus private messages to and from you. |

## Maps

| Command | Description |
|---|---|
| `/map [game_id]`, `/viewmap [game_id]` | Current board as a PNG. |
| `/replay <game_id> <turn>` | The map for a past turn. |

## Channels

Link a game to a Telegram channel and the bot posts maps, results, and broadcasts there
automatically. You must be a player in the game or an admin. Get the channel ID by
forwarding a channel message to [@userinfobot](https://t.me/userinfobot).

| Command | Description |
|---|---|
| `/link_channel <game_id> <channel_id>` | Link a channel (e.g. `-1001234567890`). |
| `/unlink_channel <game_id>` | Remove the link. |
| `/channel_info <game_id>` | Channel ID, name, and current settings. |
| `/channel_settings <game_id> <setting> <value>` | Change a setting. |

Settings: `auto_post_maps`, `auto_post_broadcasts`, `auto_post_notifications` (all
`true`/`false`, default `true`) and `notification_level` (`all`/`important`/`none`, default
`all`).

## Admin

| Command | Description |
|---|---|
| `/debug <command>` | Diagnostics. Admin only. |

## Troubleshooting

| Message | Fix |
|---|---|
| "You are not in game X" | Join it first with `/join`. |
| "Order failed" | Check the syntax and that the order type suits the current phase — `/selectunit` avoids both problems. |
| "Channel not linked" | Run `/link_channel`. |
| Bot doesn't respond | Confirm the bot and API are running and that you have sent `/register`. |

More: [FAQ and setup](LOCAL_DEVELOPMENT.md#troubleshooting).
