# Migration Plan for Diplomacy Python Rewrite

## Prioritization of Modules to Rewrite

1. **Core Game Engine**
   - Game state management
   - Turn processing and order resolution
   - Player (power) management
   - Map representation and loading
2. **Order Parsing and Validation**
3. **Basic Server Loop**
   - Accept and process game commands (CLI or API)
4. **Minimal Client Interface**
   - For testing and interaction
5. **Test Suite**
   - Unit and integration tests for core logic
6. **DAIDE Protocol Support** (after core is working)
7. **Web Interface** (optional, after core and DAIDE)
8. **Advanced Features**
   - Adjudication edge cases, map variants, etc.

## Step-by-Step Migration and Testing Strategy

1. Implement and test each core module in isolation (TDD: write tests first)
2. Integrate modules incrementally, verifying with tests at each step
3. After core is functional, add DAIDE protocol support and test
4. Optionally, add web interface and advanced features
5. Continuously update documentation and fix_plan.md as progress is made
6. Regularly run and expand test suite to ensure correctness

---

This migration plan should be updated as priorities shift or new requirements emerge during development.
