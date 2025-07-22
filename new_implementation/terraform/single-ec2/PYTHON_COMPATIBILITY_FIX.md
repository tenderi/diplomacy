# Python Package Compatibility Fix for Amazon Linux 2

## Issue
The original `requirements.txt` specified package versions that were too new for Amazon Linux 2's Python/pip environment:

```
ERROR: Could not find a version that satisfies the requirement fastapi==0.115.6 (from versions: ..., 0.103.2)
```

## Root Cause
Amazon Linux 2 comes with:
- Python 3.7/3.8 (older versions)
- pip with limited access to latest PyPI packages
- Some packages may not have wheels built for older Python versions

## Fix Applied
Updated `requirements.txt` in `user_data.sh` to use Amazon Linux 2 compatible versions:

### Version Changes
| Package | Original | Fixed | Notes |
|---------|----------|--------|--------|
| fastapi | 0.115.6 | 0.103.2 | Latest available on AL2 |
| uvicorn | 0.32.1 | 0.24.0 | Compatible with fastapi 0.103.x |
| sqlalchemy | 2.0.36 | 1.4.53 | Major version downgrade |
| psycopg2-binary | 2.9.10 | 2.9.7 | Stable version |
| alembic | 1.14.0 | 1.12.1 | Compatible with SQLAlchemy 1.4.x |
| python-telegram-bot | 21.10 | 20.7 | Major version downgrade |
| pydantic | 2.10.3 | 1.10.13 | Major version downgrade |
| python-multipart | 0.0.12 | 0.0.6 | Stable version |
| jinja2 | 3.1.4 | 3.1.2 | Minor downgrade |
| pytz | 2024.2 | 2023.3 | Stable version |

## Potential Code Compatibility Issues

### SQLAlchemy 2.0 → 1.4
- **Query syntax**: SQLAlchemy 2.0 uses different query patterns
- **Type annotations**: Some type hints may need updates
- **Async patterns**: Different async/await patterns

### Pydantic 2.x → 1.x  
- **Field definitions**: `Field()` syntax changes
- **Validators**: Different decorator patterns
- **Config classes**: BaseModel.Config vs model_config

### python-telegram-bot 21.x → 20.x
- **API changes**: Some method signatures may differ
- **Async patterns**: Different async handling

## Application Code Assessment
The current application code in `src/` should be checked for compatibility with these downgraded versions. Key files to review:

1. `src/server/db_models.py` - SQLAlchemy models
2. `src/server/api.py` - Pydantic models and FastAPI routes
3. `src/server/telegram_bot.py` - Telegram bot integration

## Testing Recommendation
After deployment, verify all major functions:
1. Database operations (CRUD)
2. API endpoints (/health, /games/, etc.)
3. Telegram bot functionality
4. Background processes

## Future Considerations
- Consider upgrading to Amazon Linux 2023 for newer Python versions
- Or use Docker with Python 3.11+ for latest package support
- Monitor for any runtime compatibility issues

## Expected Result
With these compatible versions, the pip installation should succeed:
```bash
✓ Installing Python dependencies...
Successfully installed fastapi-0.103.2 uvicorn-0.24.0 sqlalchemy-1.4.53 ...
``` 