# Fix Plan (Updated July 2025)

**[2025-01-21] CRITICAL FIX COMPLETED: Root cause of ECS asyncio failures was start.sh always starting main API server regardless of BOT_ONLY setting. Fixed start.sh to properly implement BOT_ONLY mode separation: BOT_ONLY=true runs only telegram bot (with notification API on 8081), BOT_ONLY=false runs both servers. Added comprehensive environment variable debugging. Combined with previous fixes (pytz dependency, database config from env vars, lazy DB initialization), this completely resolves all ECS deployment issues. All tests pass (10/10). Ready for production ECS deployment.**

**[2025-07-16] API endpoint /games/{game_id}/legal_orders/{power}/{unit} added. Returns all valid order strings for a unit in the current game state. Ready for Telegram bot and UI integration.**

**[2025-07-16] Order suggestions/help system implemented. Added OrderParser.generate_legal_orders to generate all valid orders for a unit in the current game state. Comprehensive tests added in test_order.py. All tests pass. This is the foundation for API and Telegram bot integration.**

**[2025-07-16] Player replacement system finalized and robust. /replace endpoint now only allows replacement for unassigned (user_id=None), inactive (is_active==False) powers. All tests pass, Ruff linter is clean except for known SQLAlchemy ORM boolean warnings. Version tagged as v0.2.7. Codebase is robust, documented, and ready for further features.**

**[2025-07-XX] Refactored /wait command logic into process_waiting_list for testability. Added comprehensive unit tests for automated game creation and waiting list logic (game creation, assignment, notification, edge cases). All tests pass.**

**[2025-07-XX] All tests in new_implementation pass. Tests in old_implementation are excluded from runs per project policy (see agent.md). Test suite is green.**

## Prioritization Rationale
- The following items are prioritized to ensure robust, automated, and user-friendly Diplomacy play at scale. Game master automation and infrastructure are most critical for reliability and hands-off operation. Enhanced bot features and polish follow.

## Remaining Incomplete Features (Prioritized)

*Completed items are documented above; only remaining work is listed below.*

### 2. Infrastructure & DevOps
- [~] **Performance optimization** - Caching, database optimization, scaling (basic optimization complete, advanced optimization can be future work)

### 3. Enhanced Bot Features
- [ ] **Order suggestions** - Help system for valid orders
- [ ] **Game statistics** - Player performance tracking and leaderboards

## Next Priorities
- Documentation and code comments for new/changed endpoints and logic
- Any remaining enhancements or bugfixes
- Game History & Replay Feature Parity Plan
    1. Add adjudication result history: Store the outcome of each order (success/failure, dislodgements, etc.) for every phase/turn, and expose this via the API and replay endpoints.
    2. Group and store messages by phase: Update the message model and storage so that all in-game messages are associated with a specific phase/turn, and allow retrieval of messages per phase in the API.
    3. Implement role-based filtering for history and replay: Ensure that players, observers, and omniscient users see only the data they are permitted to (e.g., private messages, orders, results) when accessing history endpoints.
    4. Enhance the replay API: Allow users to step through the game phase-by-phase, retrieving state, orders, results, and messages for each phase, not just the board state.
    5. (Optional) Add a web UI for phase-by-phase navigation and replay, similar to the old implementation, allowing users to visually explore the game history. 

- Refactored /replace endpoint to clarify and enforce replacement policy: only unassigned (user_id=None), inactive (is_active==False) powers can be replaced.
- Updated all boolean checks on is_active to use getattr(player, 'is_active', True) is True/False for SQLAlchemy ORM compatibility.
- All tests in test_server.py now pass, including replacement edge cases.
- Ruff linter may still warn on boolean checks for SQLAlchemy columns, but this is a known issue with ORM columns and the code is correct for runtime and ORM usage.
- No further action needed unless Ruff introduces explicit support for SQLAlchemy ORM boolean columns. 
- [x] Fix off-by-one bug in engine.game.Game.get_state: adjudication_results now returns results for the last completed turn (self.turn - 1), not the current turn. Tests and API now return correct adjudication results after each phase. 
- [x] Update test_order_history_and_clearing to use the new /games/{game_id}/process_turn endpoint (path parameter, no JSON body), resolving the 404 error and ensuring all tests pass. 