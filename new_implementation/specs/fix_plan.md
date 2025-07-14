# Core Game Functionality Priorities (Initial Plan)

- Implement core game engine logic (game state, turn processing, order resolution)
- Implement map representation and loading
- Implement player (power) management
- Implement order parsing and validation
- Implement basic server loop to accept and process game commands
- Implement minimal client interface for testing (CLI or API)
- **[IN PROGRESS] Implement test suite for core game logic and order resolution (server test suite started)**
- Document core modules and usage in README

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
