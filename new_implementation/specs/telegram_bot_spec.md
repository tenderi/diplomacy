# Telegram Bot Specification for Diplomacy Python Implementation

## Bot Command Structure (Planned)

### Game Management Commands
- `/start` - Register with the bot and get help
- `/join` - Join the game queue or create/join specific game
- `/status` - Get current game status, phase, and deadline
- `/map` - Get current map visualization with unit positions
- `/quit` - Leave current game
- `/games` - List available games to join

### Order Commands (Single Message)
- `/orders <order_list>` - Submit all orders in standard Diplomacy notation
  - Example: `/orders A PAR - BUR; F BRE - MAO; A MAR S A PAR - BUR`
  - Example: `/orders A LON - BEL VIA CONVOY; F NTH C A LON - BEL; A YOR H`
  - Semicolon-separated for multiple orders
  - Standard notation: `A/F PROVINCE - DESTINATION`, `A/F PROVINCE H`, `A/F PROVINCE S UNIT - TARGET`
- `/myorders` - Retrieve your current submitted orders for this turn
- `/clear` - Clear all your current orders for this turn

### Diplomacy Commands
- `/message @player <message>` - Send private diplomatic message
- `/broadcast <message>` - Send message to all players in current game
- `/players` - List all players in current game with their powers

### Help Commands
- `/help` - Show all available commands
- `/rules` - Show basic Diplomacy rules and order syntax
- `/examples` - Show order syntax examples

## Technical Architecture

### Order Parsing Specification
The bot will accept standard Diplomacy notation in a single message:

**Standard Order Format:**
- **Move:** `A PAR - BUR` or `F LON - NTH`
- **Hold:** `A PAR H` or `F LON H`
- **Support:** `A MAR S A PAR - BUR` or `F BRE S F MAO - SPA`
- **Convoy:** `F NTH C A LON - BEL` (fleet convoying)
- **Move via Convoy:** `A LON - BEL VIA CONVOY`

**Multi-Order Format:**
- Orders separated by semicolons: `A PAR - BUR; F BRE H; A MAR S A PAR - BUR`
- Flexible whitespace handling and case-insensitive parsing
- Validation with specific error messages for invalid orders

**Order Storage:**
- Current orders stored per player per game
- `/myorders` returns formatted list of current orders
- `/clear` removes all orders for current turn
- Orders can be updated until turn deadline

## Components Needed
1. **Telegram Bot Service** - Main bot interface using python-telegram-bot
2. **HTTP API Server** - RESTful API wrapping the existing game server
3. **Database Layer** - SQLite/PostgreSQL for user and game persistence
4. **Game Scheduler** - Background service for turn processing and deadlines
5. **Map Renderer** - Generate map images for Telegram sharing
6. **Order Parser** - Enhanced parser for single-message order submission
