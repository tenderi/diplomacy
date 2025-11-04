# Developer Guide

Guide for developers contributing to or extending the Diplomacy Python Implementation.

## Table of Contents
- [Architecture Overview](#architecture-overview)
- [Project Structure](#project-structure)
- [Code Standards](#code-standards)
- [Adding New Features](#adding-new-features)
- [Testing Guidelines](#testing-guidelines)
- [API Development](#api-development)
- [Database Schema Changes](#database-schema-changes)
- [Contributing](#contributing)

---

## Architecture Overview

### High-Level Architecture

```
┌─────────────────┐
│   Telegram Bot  │───┐
└─────────────────┘   │
                      │
┌─────────────────┐   │   ┌──────────────┐
│   REST API      │───┼───│  Game Engine │
└─────────────────┘   │   └──────────────┘
                      │          │
┌─────────────────┐   │          │
│   DAIDE Server  │───┘          │
└─────────────────┘              │
                          ┌──────────────┐
                          │  PostgreSQL  │
                          └──────────────┘
```

### Core Components

1. **Engine** (`src/engine/`): Core game logic, rules, and adjudication
2. **Server** (`src/server/`): API endpoints, Telegram bot, DAIDE protocol
3. **Database** (`src/engine/database*.py`): Data persistence layer
4. **Tests** (`src/tests/`): Comprehensive test suite

---

## Project Structure

```
new_implementation/
├── src/
│   ├── engine/          # Core game engine
│   │   ├── game.py      # Main Game class
│   │   ├── map.py       # Map handling
│   │   ├── data_models.py  # Data models
│   │   ├── database.py  # Database schema
│   │   └── database_service.py  # Database operations
│   ├── server/          # Server components
│   │   ├── api/         # REST API
│   │   │   └── routes/  # API route modules
│   │   └── telegram_bot/ # Telegram bot modules
│   └── tests/           # Test suite
├── specs/               # Specifications
├── docs/                # Documentation
└── requirements.txt     # Dependencies
```

---

## Code Standards

### Type Hints

All code must use strict type hints:

```python
from typing import List, Dict, Optional

def process_orders(
    game_id: str,
    orders: List[str]
) -> Dict[str, Any]:
    """Process orders for a game."""
    ...
```

### Linting

Code must pass Ruff linting:

```bash
ruff check src/
ruff format src/
```

### Documentation

- All public functions must have docstrings
- Use Google-style docstrings:
  ```python
  def my_function(param1: str, param2: int) -> bool:
      """Brief description.
      
      Args:
          param1: Description of param1
          param2: Description of param2
      
      Returns:
          Description of return value
      """
  ```

---

## Adding New Features

### 1. Plan the Feature

- Review `specs/` for existing specifications
- Create or update specification if needed
- Update `specs/fix_plan.md` with your feature

### 2. Implement Core Logic

- Add engine logic in `src/engine/`
- Follow existing patterns and architecture
- Ensure strict typing

### 3. Add API Endpoints

- Create route in appropriate `src/server/api/routes/` module
- Follow REST conventions
- Add request/response models in `server/models.py`

### 4. Add Database Support

- Update `src/engine/database.py` if schema changes needed
- Add methods to `src/engine/database_service.py`
- Create migration if needed

### 5. Add Tests

- Unit tests in `src/tests/test_*.py`
- Integration tests for workflows
- Ensure 100% coverage of new code

### 6. Update Documentation

- Update relevant README files
- Add to command reference if needed
- Update FAQ if applicable

---

## Testing Guidelines

### Test Structure

```python
import pytest
from engine.game import Game

class TestMyFeature:
    def setup_method(self):
        """Set up test fixtures."""
        self.game = Game(map_name='standard')
    
    @pytest.mark.unit
    def test_my_feature(self):
        """Test my feature."""
        # Arrange
        # Act
        # Assert
```

### Test Categories

- **Unit Tests**: Test individual functions/classes
- **Integration Tests**: Test component interactions
- **API Tests**: Test API endpoints
- **Database Tests**: Test database operations

### Running Tests

```bash
# All tests
pytest src/tests/ -v

# Specific category
pytest src/tests/ -v -m unit

# Specific file
pytest src/tests/test_game.py -v

# With coverage
pytest src/tests/ --cov=src --cov-report=html
```

---

## API Development

### Adding New Endpoints

1. **Create route function** in appropriate module:
   ```python
   @router.post("/my-endpoint")
   def my_endpoint(req: MyRequest) -> Dict[str, Any]:
       """My endpoint description."""
       ...
   ```

2. **Add request/response models**:
   ```python
   class MyRequest(BaseModel):
       field1: str
       field2: Optional[int] = None
   ```

3. **Register route** in `_api_module.py`:
   ```python
   app.include_router(my_module.router)
   ```

4. **Add tests**:
   ```python
   def test_my_endpoint(client):
       response = client.post("/my-endpoint", json={...})
       assert response.status_code == 200
   ```

---

## Database Schema Changes

### Adding New Columns

1. **Update model** in `src/engine/database.py`:
   ```python
   class MyModel(Base):
       new_field = Column(String(255), nullable=True)
   ```

2. **Add migration** (optional, schema auto-updates):
   ```python
   # alembic/versions/xxx_add_new_field.py
   def upgrade():
       op.add_column('my_table', sa.Column('new_field', sa.String(255)))
   ```

3. **Update database service**:
   ```python
   def get_my_model(self, id: int) -> MyModel:
       # Include new_field in query
   ```

4. **Schema auto-update**:
   - Schema auto-updates on server start
   - Check `_api_module.py` for column detection logic

---

## Contributing

### Workflow

1. Create feature branch
2. Implement feature with tests
3. Ensure all tests pass
4. Update documentation
5. Submit pull request

### Checklist

- [ ] Code follows style guidelines
- [ ] All tests pass
- [ ] New tests added for new features
- [ ] Documentation updated
- [ ] Type hints added
- [ ] Ruff checks pass
- [ ] No breaking changes (or documented)

### Code Review

- Code will be reviewed for:
  - Correctness
  - Style compliance
  - Test coverage
  - Documentation quality

---

## Module-Specific Guidelines

### Engine Module

- Pure game logic, no I/O
- Stateless where possible
- Comprehensive error handling
- Well-documented algorithms

### Server Module

- RESTful API design
- Proper HTTP status codes
- Input validation
- Error responses with details

### Database Module

- Use transactions appropriately
- Handle connection errors gracefully
- Use indexes for performance
- Document schema changes

---

## Performance Considerations

- Use database indexes for frequent queries
- Cache expensive operations (maps, etc.)
- Use connection pooling for production
- Monitor query performance

---

## Debugging

### Logging

```python
import logging
logger = logging.getLogger("diplomacy.module")

logger.debug("Detailed debug info")
logger.info("General information")
logger.warning("Warning message")
logger.error("Error message")
```

### Common Issues

1. **Import errors**: Check Python path and imports
2. **Database errors**: Verify connection and schema
3. **Test failures**: Run with `-v` for verbose output
4. **Type errors**: Ensure all type hints are correct

---

## Additional Resources

- [Architecture Spec](./architecture.md)
- [Data Spec](./data_spec.md)
- [API Documentation](../src/server/README.md)
- [Engine Documentation](../src/engine/README.md)

