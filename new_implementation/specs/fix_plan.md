# Core Game Functionality Priorities (Initial Plan)

- Implement core game engine logic (game state, turn processing, order resolution)
- Implement map representation and loading
- Implement player (power) management
- Implement order parsing and validation
- Implement basic server loop to accept and process game commands
- Implement minimal client interface for testing (CLI or API)
- **[IN PROGRESS] Implement test suite for core game logic and order resolution (server test suite started)**
- Document core modules and usage in README
- **[IN PROGRESS] Implement advanced order adjudication and turn processing (real Diplomacy rules, not just stubs)**

# Top Priorities (as of July 2025)

- [ ] Implement advanced order adjudication and turn processing (edge cases, convoy paradoxes, support cut, standoffs, dislodgement)
- [ ] Expand test coverage for adjudication edge cases (convoy paradoxes, support cut, standoffs, dislodgement)
- [ ] Implement and test DAIDE protocol support for bot/server communication
- [ ] Add support for multiple concurrent games and test isolation
- [ ] Implement SAVE_GAME and LOAD_GAME commands for persistence
- [ ] Add REMOVE_PLAYER and ADVANCE_PHASE commands as per extensibility section
- [ ] Improve error response structure and consistency (see server_spec.md error handling)
- [ ] Enhance logging: add startup/shutdown, game state changes, and structured log output
- [ ] Add configuration options for host/port, persistence backend, debug/production mode, and logging
- [ ] Review and update all documentation/specs to match current implementation and new features

# Secondary Priorities (After Core is Working)

- Implement DAIDE protocol support for bot/server communication
- Implement web interface (optional, after core and DAIDE)
- Implement advanced features (adjudication edge cases, variants, etc.)
- Expand test coverage (integration, edge cases)
- Add logging and error handling improvements

# Iterative Review and Update
- Regularly review progress on all modules and specs.
- After each implementation or test, update this file to reflect completed/incomplete status.
- Adjust priorities as new requirements or issues are discovered.
- Use subagents or parallel review to accelerate code and spec analysis.
- Remove completed items and add new tasks as needed.
- Always keep this file up to date with the current project state.

# Notes
- Always create or update tests before implementing new features.
- Update this plan as progress is made or priorities shift.

# Completed Tasks
- Implemented functional Server class in server.py to support game creation, player addition, order setting, turn processing, and game state queries.
- Implemented minimal but real Game class in engine/game.py to support server operations and tests.
- Added type annotations to resolve type errors and ensure compatibility with server logic.
- All server tests now pass.
- Basic server loop and command processing implemented in server.py
- Game class implemented to support server operations
- All server tests pass as of 0.0.0
- Initial tag 0.0.0 created and pushed
- Expanded server test coverage in test_server.py to cover all major commands, error handling, and state queries as per the server specification.
- All new and existing server tests pass.
- Created and pushed git tag 0.0.1 after expanding server test coverage and passing all tests.
- Implemented minimal Client class in client.py for server interaction.
- Added client-server integration tests in tests/test_client.py covering command flow and error handling.
- All client-server tests pass.
- Created and pushed git tag 0.0.2 after implementing the minimal client and passing all integration tests.
- Added logging to the Server class for all command processing, errors, and key actions to improve debuggability and meet requirements for enhanced error handling and logging.
- All server and client-server integration tests pass after logging changes.
- Created and pushed git tag 0.0.3 after adding logging and improved error handling to the server.
- Expanded Game class to use Map and Power for real state management. add_player now creates a Power object, and get_state exposes powers.
- All engine-level tests pass after this change.
- Created and pushed git tag 0.0.4 after expanding the Game class to use Map and Power for real state management.
- Implement full order parsing and validation in OrderParser (no longer a stub; now checks power, unit, action, and target; more advanced checks TODO).
- Expanded test_order.py to cover valid/invalid parsing and validation cases.
- All order tests pass.
- Enforced strict type annotations for all fields and methods in engine, server, and client modules.
- All core and integration tests pass after typing improvements.
- Implemented map_name support, get_locations, get_adjacency, and validate_location in Map class.
- Added and passed tests for new Map API (locations, adjacency, validation).

- Enforced strict type annotations for all fields and methods in engine, server, and client modules.
- All core and integration tests pass after typing improvements.
- Implemented map_name support, get_locations, get_adjacency, and validate_location in Map class.
- Added and passed tests for new Map API (locations, adjacency, validation).
- Fixed convoyed move adjudication bug by correcting order parsing for multi-word convoy targets and implementing proper convoy availability checking.
- Fixed dislodgement logic bug by implementing correct Diplomacy rules where attacker must have greater strength than defender to succeed (equal strength = standoff).
- Updated test_convoyed_move to properly test supported convoyed attack (strength 2) vs defender (strength 1).
- All adjudication tests now pass with proper Diplomacy rule implementation.

# Bugs
- No known bugs at this time. All tests passing.

# Previously Fixed Bugs
- [x] BUG: Convoyed move adjudication is incorrect. Army does not move to destination when convoyed (see test_convoyed_move failure in test_adjudication.py).
  - FIXED: Corrected OrderParser to handle multi-word convoy targets (e.g., "A LON - BEL" instead of just "A")
  - FIXED: Implemented proper convoy availability checking in adjudication logic
  - FIXED: Updated test to use supported attack for proper convoy success demonstration
- [x] BUG: Dislodgement logic is incorrect. Defending unit is not removed from province when dislodged (see test_dislodgement failure in test_adjudication.py).
  - FIXED: Implemented correct Diplomacy rules where attacker needs greater strength (not equal) to succeed
  - FIXED: Equal strength attacks now properly result in standoffs as per official Diplomacy rules
  - FIXED: Dislodgement now works correctly when supported attacks overcome defending units
