# Fix Plan (Updated July 2025)

**[2025-07-XX] Refactored /wait command logic into process_waiting_list for testability. Added comprehensive unit tests for automated game creation and waiting list logic (game creation, assignment, notification, edge cases). All tests pass.**

**[2025-07-XX] All tests in new_implementation pass. Tests in old_implementation are excluded from runs per project policy (see agent.md). Test suite is green.**

## Prioritization Rationale
- The following items are prioritized to ensure robust, automated, and user-friendly Diplomacy play at scale. Game master automation and infrastructure are most critical for reliability and hands-off operation. Enhanced bot features and polish follow. Observer mode is lowest priority per user instruction.

## Incomplete Features (Prioritized)

### 1. Game Master Automation (highest priority)
- [ ] **Automated game creation** - Bot-initiated games when enough players join
- [ ] **Turn deadline enforcement** - Automatic processing when deadlines expire (ensure reliability and notification)
- [ ] **Player replacement system** - Handle disconnected/inactive players

### 2. Infrastructure & DevOps
- [ ] **Production deployment** - Docker containerization and deployment scripts
- [ ] **Monitoring and logging** - Comprehensive system monitoring
- [ ] **Performance optimization** - Caching, database optimization, scaling
- [ ] **Security hardening** - Authentication, authorization, input validation

### 3. Enhanced Bot Features
- [ ] **Map visualization** - Generate and send map images showing current game state (improve UX, support for all variants)
- [ ] **Order suggestions** - Help system for valid orders
- [ ] **Game statistics** - Player performance tracking and leaderboards
- [ ] **Multi-language support** - Internationalization for different Telegram users

### 4. Observer Mode (lowest priority)
- [ ] **Observer mode** - Spectator functionality for watching games

## Next Priorities
- Documentation and code comments for new/changed endpoints and logic
- Observer mode (lowest priority)
- Any remaining enhancements or bugfixes

## Game History & Replay Feature Parity Plan
1. Add adjudication result history: Store the outcome of each order (success/failure, dislodgements, etc.) for every phase/turn, and expose this via the API and replay endpoints.
2. Group and store messages by phase: Update the message model and storage so that all in-game messages are associated with a specific phase/turn, and allow retrieval of messages per phase in the API.
3. Implement role-based filtering for history and replay: Ensure that players, observers, and omniscient users see only the data they are permitted to (e.g., private messages, orders, results) when accessing history endpoints.
4. Enhance the replay API: Allow users to step through the game phase-by-phase, retrieving state, orders, results, and messages for each phase, not just the board state.
5. (Optional) Add a web UI for phase-by-phase navigation and replay, similar to the old implementation, allowing users to visually explore the game history. 