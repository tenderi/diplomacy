# Telegram Bot Command Reference

Complete reference for all Telegram bot commands available in the Diplomacy game bot.

## Table of Contents
- [Getting Started](#getting-started)
- [Game Management](#game-management)
- [Order Submission](#order-submission)
- [Interactive Orders](#interactive-orders)
- [Messages & Communication](#messages--communication)
- [Maps & Visualization](#maps--visualization)
- [Channel Management](#channel-management)
- [Admin Commands](#admin-commands)
- [Menu Buttons](#menu-buttons)

---

## Getting Started

### `/start`
Welcome message and main menu. Shows available commands and features.

**Usage**: `/start`

**Response**: Displays welcome message with interactive keyboard menu.

---

### `/register`
Register yourself as a user in the system. Required before joining games.

**Usage**: `/register`

**Response**: Confirms registration and shows your user ID.

**Example**:
```
/register
→ 🎉 Registration successful!
  Welcome John Doe (ID: 12345)
```

---

## Game Management

### `/games`
List all games you're currently participating in.

**Usage**: `/games`

**Response**: Shows list of your active games with game IDs, your power, and current phase.

**Example**:
```
/games
→ Your Games:
  • Game 42 - FRANCE (Spring 1901 Movement)
  • Game 55 - GERMANY (Autumn 1902 Retreat)
```

---

### `/join`
Join a specific game by game ID.

**Usage**: `/join <game_id>`

**Example**: `/join 42`

**Response**: Shows available powers or confirms your power assignment.

**Note**: If the game has open powers, you'll be shown a selection menu.

---

### `/quit`
Leave a game you're currently playing.

**Usage**: `/quit <game_id>`

**Example**: `/quit 42`

**Response**: Confirms you've left the game.

**Note**: Your power will become available for replacement.

---

### `/replace`
Replace a vacated power in a game.

**Usage**: `/replace <game_id> <power>`

**Example**: `/replace 42 ITALY`

**Response**: Confirms you've replaced the vacated power.

---

### `/wait`
Join the waiting list for automatic game matching. When 7 players are on the waiting list, a new game is automatically created.

**Usage**: `/wait`

**Response**: Confirms you've joined the waiting list and shows current player count.

**Example**:
```
/wait
→ ⏳ Joined waiting list!
  Current players: 3/7
  Waiting for 4 more players...
```

---

## Order Submission

### `/order`
Submit orders for a game. If you're in only one game, you can omit the game_id.

**Usage**: `/order [game_id] <order1>; <order2>; ...`

**Examples**:
- `/order A PAR - BUR`
- `/order 42 A PAR - BUR; F MAR H`

**Response**: Shows success/failure status for each order.

**Note**: Multiple orders can be separated by semicolons (`;`).

---

### `/orders`
Submit orders for a specific game (requires game_id).

**Usage**: `/orders <game_id> <order1>; <order2>; ...`

**Example**: `/orders 42 A PAR - BUR; F MAR H`

**Response**: Shows success/failure status for each order.

---

### `/myorders`
View your submitted orders for a game.

**Usage**: `/myorders [game_id]`

**Example**: `/myorders 42`

**Response**: Shows all your current orders for the game.

---

### `/clearorders`
Clear all your submitted orders for a game.

**Usage**: `/clearorders [game_id]`

**Example**: `/clearorders 42`

**Response**: Confirms all orders have been cleared.

**Note**: You can resubmit orders after clearing.

---

### `/orderhistory`
View the order history for a game.

**Usage**: `/orderhistory <game_id>`

**Example**: `/orderhistory 42`

**Response**: Shows all orders submitted for previous turns, grouped by turn and power.

---

### `/processturn`
Process the current turn (advance phase and adjudicate orders).

**Usage**: `/processturn <game_id>`

**Example**: `/processturn 42`

**Response**: Confirms turn processing and shows new phase information.

**Note**: Only players in the game can process turns.

---

## Interactive Orders

### `/selectunit`
Interactive unit selection for easier order submission. Shows a menu of your units.

**Usage**: `/selectunit <game_id>`

**Example**: `/selectunit 42`

**Response**: Shows interactive buttons for each of your units. Click a unit to see its possible moves.

**Features**:
- Visual unit selection
- Move options displayed as buttons
- Convoy options for fleets
- One-click order submission

---

## Messages & Communication

### `/message`
Send a private message to another player in a game.

**Usage**: `/message <game_id> <power> <message>`

**Example**: `/message 42 ENGLAND Hello, want to discuss an alliance?`

**Response**: Confirms message sent.

**Note**: Only the specified power will receive the message.

---

### `/broadcast`
Send a broadcast message to all players in a game.

**Usage**: `/broadcast <game_id> <message>`

**Example**: `/broadcast 42 I propose a Western Triple Alliance!`

**Response**: Confirms broadcast sent.

**Note**: All players in the game will receive the broadcast. If the game is linked to a Telegram channel, the broadcast will also be posted there.

---

### `/messages`
View all messages for a game (broadcasts and private messages sent to/from you).

**Usage**: `/messages [game_id]`

**Example**: `/messages 42`

**Response**: Shows all relevant messages for the game.

---

## Maps & Visualization

### `/map`
View the current game map.

**Usage**: `/map [game_id]`

**Example**: `/map 42`

**Response**: Sends the current game map as an image.

**Note**: If no game_id is provided and you're in only one game, that game's map is shown.

---

### `/viewmap`
Alias for `/map` - view the current game map.

**Usage**: `/viewmap [game_id]`

**Example**: `/viewmap 42`

---

### `/replay`
View the map for a specific turn in game history.

**Usage**: `/replay <game_id> <turn>`

**Example**: `/replay 42 5`

**Response**: Sends the map image for the specified turn.

---

### `/refresh_map`
Refresh the cached map for a game (admin/debugging command).

**Usage**: `/refresh_map <game_id>`

**Example**: `/refresh_map 42`

---

## Channel Management

### `/link_channel`
Link a Telegram channel to a game for automated posting.

**Usage**: `/link_channel <game_id> <channel_id>`

**Example**: `/link_channel 42 -1001234567890`

**Response**: Confirms channel linked and explains automated features.

**Features Enabled**:
- Maps posted after each turn
- Broadcasts forwarded to channel
- Turn notifications sent

**Note**: 
- You must be a player in the game or an admin
- To get channel ID: forward a message from the channel to @userinfobot or use @getidsbot

---

### `/unlink_channel`
Unlink a Telegram channel from a game.

**Usage**: `/unlink_channel <game_id>`

**Example**: `/unlink_channel 42`

**Response**: Confirms channel unlinked.

---

### `/channel_info`
Get information about a game's linked channel.

**Usage**: `/channel_info <game_id>`

**Example**: `/channel_info 42`

**Response**: Shows channel ID, name, and current settings.

---

### `/channel_settings`
Update channel settings for automated posting.

**Usage**: `/channel_settings <game_id> <setting> <value>`

**Settings**:
- `auto_post_maps` - true/false (default: true)
- `auto_post_broadcasts` - true/false (default: true)
- `auto_post_notifications` - true/false (default: true)
- `notification_level` - all/important/none (default: all)

**Examples**:
- `/channel_settings 42 auto_post_maps false`
- `/channel_settings 42 notification_level important`

**Response**: Confirms setting updated.

---

## Admin Commands

### `/debug`
Debug command for troubleshooting (admin only).

**Usage**: `/debug <command>`

**Note**: Admin-only command (user ID: 8019538).

---

## Menu Buttons

The bot provides an interactive keyboard menu with the following buttons:

- **🎯 Register** - Register as a new user
- **🎮 My Games** - List your active games
- **🎲 Join Game** - Join a specific game
- **⏳ Join Waiting List** - Join automated game matching
- **📋 My Orders** - View your orders
- **🗺️ View Map** - View current game map
- **💬 Messages** - View messages
- **ℹ️ Help** - Show help information
- **⚙️ Admin** - Admin menu (admin only)

---

## Tips & Best Practices

1. **Order Format**: Use standard Diplomacy notation:
   - `A PAR - BUR` (Army moves)
   - `F MAR H` (Fleet holds)
   - `A PAR - BUR S A MAR - BUR` (Support)
   - `F ENG C A LON - BRE` (Convoy)

2. **Multiple Orders**: Separate orders with semicolons (`;`)

3. **Game ID**: If you're in only one game, you can often omit the game_id

4. **Interactive Orders**: Use `/selectunit` for easier order submission with visual selection

5. **Channel Integration**: Link games to Telegram channels for automated map posting and notifications

6. **Deadlines**: Set deadlines for games using the API to ensure timely order submission

---

## Troubleshooting

**"You are not in game X"**: Make sure you've joined the game with `/join` first.

**"Order failed"**: Check the order syntax and ensure it's valid for the current phase.

**"Channel not linked"**: Use `/link_channel` to link a Telegram channel to your game.

**"Bot not responding"**: Check that the bot is running and your Telegram ID is registered.

For more help, see the [FAQ and Troubleshooting Guide](../docs/FAQ.md).

