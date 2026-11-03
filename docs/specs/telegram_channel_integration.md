# Telegram Channel Integration

A game can be **linked to a Telegram channel**, turning it from a private bot conversation
into a shared, semi-public experience: maps, results, and broadcasts are posted
automatically while orders and private diplomacy stay in DMs with the bot.

## Setup

1. Create a group and add every player plus the bot, giving it permission to send messages
   and photos.
2. In the group, `/linkgroup <game_id>` (or `/newgame` for a new game) — you must be a player
   in the game. Or use the game web page's "Link a Telegram group", which opens
   `t.me/<bot>?startgroup=link_<game_id>`: Telegram adds the bot to the group you pick and
   sends `/start link_<game_id>` there, which links the same way. Once linked, the web page
   names the group and has an Unlink button (players of the game only; it asks for
   confirmation, and the group is told it was unlinked, without naming who did it). A group has at most one
   game; see [`TELEGRAM_BOT_COMMANDS.md`](../TELEGRAM_BOT_COMMANDS.md) for moving it.
3. `/channel_settings <game_id> <setting> <value>` to tune what gets posted.

**A game is linked only from inside the group**, with the chat id the bot saw the command
in. `POST /games/{id}/channel/link` takes the bot secret (or the admin token), never a web
login, and `/link_channel` takes no chat id: if any chat id were accepted, a player
who knew a group's id could link their game to a group they are not in, and its members could
then neither start nor link a game there. A broadcast *channel*, where the bot can't read
commands, can be linked only by an admin through the API.

Commands: `/linkgroup`, `/unlinkgroup`, `/unlink_channel`, `/channel_info`, `/channel_settings` — see
[`TELEGRAM_BOT_COMMANDS.md`](../TELEGRAM_BOT_COMMANDS.md).

## What gets posted

| Trigger | Content |
|---|---|
| Phase change / new turn | Board map, supply-center counts per power, phase info, deadline. |
| Adjudication complete | Battle results: successful attacks, bounces, dislodgements, supply-center changes. |
| Player broadcast | The message, attributed to its power. |
| Deadline approaching | Reminder with the per-power order-submission status. |
| Game end | The result as text (victory, draw, last power standing, nobody wins). A game-ending *turn* also posts its turn maps like any other; a draw or concession posts text only. |

## What stays private

Individual orders and private diplomatic messages. The channel sees the public board, not
anyone's intentions. The deadline reminder does name the powers still to come ("still to
come: ..."), but not what anyone ordered.

## Settings

| Setting | Values | Default |
|---|---|---|
| `auto_post_maps` | `true` / `false` | `true` |
| `auto_post_broadcasts` | `true` / `false` | `true` |
| `auto_post_notifications` | `true` / `false` | `true` |
| `notification_level` | `all` / `important` / `none` | `all` |

`notification_level` filters the automatic notification text (the API rejects any other value
with a 422 naming the three):

- `all`: every post.
- `important`: only the turn-processed post, game endings (victory, draw, last power standing,
  nobody wins), eliminations, concessions, and posts a player sent to the group themselves
  (broadcasts). Joins, quits and takeovers, deadline set or proposal notices, deadline reminders
  and stuck-phase notices are skipped.
- `none`: no automatic notification text; posts a player sent themselves (broadcast) still go,
  since the player asked for them.

`auto_post_notifications: false` silences the automatic text at any level, and `auto_post_maps`
alone governs the turn map rows, whatever the level.

## Implementation

- **API** (`src/server/api/routes/channels.py`): link, unlink, get/update settings, and
  posts queued for the group: a broadcast, the player dashboard, the timeline, a map, a
  discussion thread.
- **Bot** (`src/server/telegram_bot/channels.py`, `channel_commands.py`): the commands above
  plus the formatting and posting helpers.
- **Persistence**: channel link and settings hang off the game row (`channel_id`,
  `channel_settings`).
- **Hooks**: automatic group text goes through `post_to_game_group` (`api/shared.py`), gated
  by `auto_post_notifications` and `notification_level`: each call site passes a `GroupPost`
  (`ROUTINE`, `IMPORTANT` or `PLAYER_SENT`) saying which levels let it through; the turn-processed
  post in `_post_turn_to_channel` is `IMPORTANT`. `auto_post_maps` gates only the turn map rows.
  The API queues everything for Telegram in the `bot_outbox` table, pulled and
  sent by the bot: player DMs (`kind="dm"`) on turn processing, deadline reminders,
  broadcasts and game end, and group posts (`kind="channel_text"`,
  `"channel_create_thread"`) from the `/games/{id}/channel/*` routes. `telegram_bot/channels.py`
  only *formats* those posts (timeline, player dashboard); nothing in the
  bot sends to a group except the outbox loop. All group posts use legacy
  `parse_mode='Markdown'`: bold is `*single*`.
- **After every processed turn** the group gets the notification and two `kind="channel_map"`
  rows: the turn's orders on the board they were given on (`/games/{id}/map/turn/{k}/orders`)
  and the board they produced (`/games/{id}/map/history/{k+1}`), both fetched by turn number
  (`docs/specs/architecture.md` §Notifications has the details).

## Out of scope

Discord bridging, spectator mode, tournament integration, AI-powered analysis, live
streaming, and web/mobile/email digests of channel content. See
[`fix_plan.md`](fix_plan.md).
