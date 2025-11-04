# FAQ and Troubleshooting Guide

Common questions and solutions for the Diplomacy Python Implementation.

## Table of Contents
- [Installation & Setup](#installation--setup)
- [Game Play](#game-play)
- [Telegram Bot](#telegram-bot)
- [API & Server](#api--server)
- [Database](#database)
- [Errors & Issues](#errors--issues)
- [Performance](#performance)

---

## Installation & Setup

### Q: How do I install the dependencies?

**A**: Install requirements from the requirements file:
```bash
pip install -r requirements.txt
```

Make sure you have Python 3.8+ installed.

---

### Q: Do I need a database?

**A**: Yes, for production use. The system uses PostgreSQL:
```bash
# Set environment variable
export SQLALCHEMY_DATABASE_URL=postgresql+psycopg2://user:pass@host/db
```

For testing without a database, many tests will skip gracefully.

---

### Q: How do I set up the Telegram bot?

**A**: 
1. Create a bot with [@BotFather](https://t.me/BotFather) on Telegram
2. Get your bot token
3. Set environment variable:
   ```bash
   export TELEGRAM_BOT_TOKEN=your-token-here
   ```
4. Start the bot:
   ```bash
   python -m server.telegram_bot
   ```

---

## Game Play

### Q: How do I start a new game?

**A**: 
- **Via Telegram Bot**: Use `/join` to join an existing game or `/wait` for automatic matching
- **Via API**: `POST /games/create` with `{"map_name": "standard"}`
- **Via CLI**: In server CLI, type `CREATE_GAME standard`

---

### Q: How do I submit orders?

**A**: 
- **Telegram Bot**: `/order <game_id> <order>` or `/order <order>` if in one game
- **API**: `POST /games/set_orders` with game_id, power, and orders array
- **CLI**: `SET_ORDERS <game_id> <power> <order>`

**Example**: `/order 42 A PAR - BUR`

---

### Q: What order formats are supported?

**A**: Standard Diplomacy notation:
- Move: `A PAR - BUR` (Army Paris to Burgundy)
- Hold: `A PAR H` (Army Paris holds)
- Support: `A PAR - BUR S A MAR - BUR` (Support move)
- Convoy: `F ENG C A LON - BRE` (Convoy army)
- Build: `A PAR B` (Build army in Paris)
- Destroy: `A PAR D` (Destroy army in Paris)
- Retreat: `A PAR - PIC` (Retreat to Picardy)

---

### Q: How do I process a turn?

**A**: 
- **Telegram Bot**: `/processturn <game_id>`
- **API**: `POST /games/{game_id}/process_turn`
- **CLI**: `PROCESS_TURN <game_id>`

This advances the game to the next phase and adjudicates all orders.

---

### Q: What happens if I don't submit orders?

**A**: 
- If a deadline is set and passes, the turn is processed automatically
- Players who don't submit orders may be marked inactive
- You can still submit orders for the next turn

---

## Telegram Bot

### Q: The bot doesn't respond to my commands

**A**: Check:
1. Bot token is set correctly: `echo $TELEGRAM_BOT_TOKEN`
2. Bot is running: Check process/logs
3. API server is running and accessible
4. Your Telegram ID is registered: Use `/register`

---

### Q: How do I get my Telegram ID?

**A**: 
- Send a message to [@userinfobot](https://t.me/userinfobot)
- Or use `/register` in the bot - it will show your ID

---

### Q: How do I link a game to a Telegram channel?

**A**: 
1. Get your channel ID:
   - Forward a message from the channel to @userinfobot
   - Or use @getidsbot in the channel
2. Link the channel: `/link_channel <game_id> <channel_id>`
3. Verify: `/channel_info <game_id>`

**Note**: You must be a player in the game or an admin.

---

### Q: What commands are available?

**A**: See the [Telegram Bot Command Reference](./TELEGRAM_BOT_COMMANDS.md) for a complete list.

---

## API & Server

### Q: How do I start the API server?

**A**: 
```bash
python -m server._api_module
# or
uvicorn server._api_module:app --host 0.0.0.0 --port 8000
```

The server will start on `http://localhost:8000` by default.

---

### Q: How do I check if the server is running?

**A**: 
- Health check: `GET http://localhost:8000/health`
- Scheduler status: `GET http://localhost:8000/scheduler/status`

---

### Q: What are the main API endpoints?

**A**: 
- `POST /games/create` - Create game
- `POST /games/{id}/join` - Join game
- `POST /games/set_orders` - Submit orders
- `POST /games/{id}/process_turn` - Process turn
- `GET /games/{id}/state` - Get game state
- See [server/README.md](../src/server/README.md) for complete list

---

### Q: How do I handle authentication?

**A**: 
- Most endpoints require `telegram_id` in the request body
- Users must be registered: `POST /users/persistent_register`
- Authorization is enforced: only the assigned user can act for a power

---

## Database

### Q: How do I set up the database?

**A**: 
1. Install PostgreSQL
2. Create database: `createdb diplomacy_db`
3. Set environment variable:
   ```bash
   export SQLALCHEMY_DATABASE_URL=postgresql+psycopg2://user:pass@localhost/diplomacy_db
   ```
4. Start the API server - schema will be created automatically

---

### Q: The database schema is missing columns

**A**: 
- The schema auto-updates on server start
- Check logs for schema update messages
- Manually add columns if needed (see `src/engine/database.py`)

---

### Q: How do I reset the database?

**A**: 
```bash
# Drop and recreate
dropdb diplomacy_db
createdb diplomacy_db
# Schema will be recreated on next server start
```

---

## Errors & Issues

### Q: "Game not found" error

**A**: 
- Check the game_id is correct
- Verify the game exists: `GET /games/{id}/state`
- Ensure you're using the correct game_id format (string or int)

---

### Q: "You are not in game X" error

**A**: 
- Join the game first: `/join <game_id>` or `POST /games/{id}/join`
- Verify you're registered: `/register` or `POST /users/persistent_register`

---

### Q: "Order failed" error

**A**: 
- Check order syntax (see [Game Play](#game-play) section)
- Verify it's valid for current phase (Movement/Retreat/Build)
- Ensure the unit exists and can perform the order
- Check province names are correct (case-insensitive)

---

### Q: "Database connection error"

**A**: 
- Verify PostgreSQL is running: `pg_isready`
- Check database URL is correct
- Ensure database exists: `psql -l | grep diplomacy`
- Check connection credentials

---

### Q: Tests are failing

**A**: 
- Check database URL is set (many tests skip without it)
- Run specific test: `pytest src/tests/test_file.py::test_name -v`
- Check test output for specific error messages
- Ensure all dependencies are installed

---

### Q: Import errors when running code

**A**: 
- Ensure you're in the correct directory
- Check Python path includes `src/` directory
- Install dependencies: `pip install -r requirements.txt`
- Use absolute imports: `from server.module import ...`

---

## Performance

### Q: The server is slow

**A**: 
- Check database connection pool settings
- Use database indexes (they're created automatically)
- Consider using a connection pooler (PgBouncer) for production
- Monitor database query performance

---

### Q: Map generation is slow

**A**: 
- Maps are cached - first generation may be slow
- Subsequent requests use cached maps
- Check disk space for map cache files
- Use `/refresh_map` to clear cache if needed

---

### Q: How do I scale horizontally?

**A**: 
- Use a load balancer (Nginx, Traefik) in front of multiple app instances
- Use a connection pooler (PgBouncer) for database connections
- Ensure all instances share the same database
- Use Docker Compose with multiple app containers

---

## Getting More Help

- **Documentation**: See `docs/` directory and `specs/` directory
- **Logs**: Check server logs for detailed error messages
- **Tests**: Run tests to verify functionality: `pytest src/tests/`
- **GitHub Issues**: Report bugs or request features

---

## Common Configuration

### Environment Variables

```bash
# Required
TELEGRAM_BOT_TOKEN=your-bot-token
SQLALCHEMY_DATABASE_URL=postgresql+psycopg2://user:pass@host/db

# Optional
DIPLOMACY_LOG_LEVEL=INFO
DIPLOMACY_LOG_FILE=/path/to/logfile
API_URL=http://localhost:8000
BOT_ONLY=false
SKIP_MAP_PREGEN=false
```

---

## Still Need Help?

If you're still experiencing issues:
1. Check the logs for detailed error messages
2. Verify all environment variables are set correctly
3. Ensure all dependencies are installed
4. Review the test suite to see expected behavior
5. Check the [specs/](../specs/) directory for detailed specifications

