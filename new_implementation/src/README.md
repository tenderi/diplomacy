# Diplomacy Server (Spec-only DAL)

## Overview
This server implements the Diplomacy API and DAIDE bridge using a single source of truth:
- Data model: `specs/data_spec.md` and `engine/data_models.py`
- Persistence: `engine/database_service.DatabaseService`
- API Models: `server/models.py` (Pydantic v2)

## Run
- Set database URL in env (PostgreSQL recommended):
```
export SQLALCHEMY_DATABASE_URL=postgresql+psycopg2://user:pass@host/db
```
- Start API:
```
python -m server.api
```

## Key Endpoints
- POST `/games/create` → `{ game_id }`
- POST `/games/{game_id}/join`
- POST `/games/set_orders` (engine-validated, DAL-persisted)
- POST `/games/{game_id}/process_turn`
- GET  `/games/{game_id}/state` → spec-shaped `GameStateOut`

## DAIDE
- TCP server in `server/daide_protocol.py`:
  - HLO creates a DAL-backed game and adds the power
  - ORD validates orders with engine and persists via DAL

## Testing
- Integration and API tests live in `src/tests/`
- Requires `SQLALCHEMY_DATABASE_URL` to be set; tests auto-skip if absent
```
pytest -q src/tests
```

## Notes
- Legacy DB modules removed. API exclusively uses `DatabaseService`.
- Follow strict typing and Ruff. Use Pydantic v2 `.model_dump()` in boundaries.
