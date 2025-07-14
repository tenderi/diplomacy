# Old Implementation: Architecture and Module Overview

This document summarizes the architecture and major modules of the original Diplomacy board game server (old_implementation), for reference during the Python rewrite.

## Major Modules and Features

- **Client**: Handles network game instances, connections, notifications, and responses.
- **Communication**: Manages requests, responses, and notifications between components.
- **DAIDE**: Implements the DAIDE protocol for bot/server communication, including message parsing and server logic.
- **Engine**: Core game logic, including game state, map, message handling, power (player) logic, and rendering.
- **Integration**: Interfaces for webdiplomacy.net and other APIs.
- **Maps**: Map files and related logic.
- **Server**: Server logic, user management, scheduling, and request handling.
- **Utils**: Utility functions, constants, error handling, and data structures.
- **Web**: Web interface (React frontend, Python backend for serving and conversion).

## Architecture and Data Flow

- The engine is the core, managing game state, rules, and processing turns.
- Communication between client/server and bots is handled via DAIDE and custom protocols.
- The server manages games, users, and network connections.
- The web interface allows users to play and visualize games.
- Utilities and map logic support the main modules.

## Reference

Use this document to map features and modules to the new implementation, and to ensure all critical functionality is ported or improved.
