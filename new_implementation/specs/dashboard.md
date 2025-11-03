# Telegram Bot Dashboard Implementation Plan

## Overview

Create a web dashboard accessible via the existing FastAPI application that provides monitoring and management capabilities for the telegram bot and related services. The dashboard will be a simple HTML/CSS/JavaScript application served at `/dashboard` with backend API endpoints for service management.

## Architecture

- **Frontend**: Simple HTML/CSS/JavaScript (no build step required)
- **Backend**: New FastAPI endpoints in `src/server/api.py`
- **Service Management**: Use systemd commands via subprocess for service control
- **Logs**: Read from systemd journal using `journalctl`
- **Database**: Query via existing `DatabaseService` with read-only operations
- **Routing**: Serve static dashboard files via FastAPI at `/dashboard` route

## Components

### 1. Backend API Endpoints (`src/server/api.py`)

#### Service Management

- `GET /dashboard/api/services/status` - Get status of `diplomacy.service` and `diplomacy-bot.service`
  - Returns: `{"services": [{"name": "diplomacy", "status": "active", "active_since": "...", ...}, ...]}`

- `POST /dashboard/api/services/restart` - Restart a service
  - Body: `{"service": "diplomacy-bot"}` or `{"service": "diplomacy"}`
  - Uses: `systemctl restart <service>`

#### Logs

- `GET /dashboard/api/logs/{service}` - Get logs for a service
  - Params: `service` (diplomacy or diplomacy-bot), optional `lines` (default 100), optional `since` (time filter)
  - Uses: `journalctl -u <service> -n <lines> --no-pager`
  - Returns: `{"logs": ["...", ...]}`

- `GET /dashboard/api/logs/stream/{service}` - Stream logs (SSE or polling endpoint)
  - For real-time log viewing (optional enhancement)

#### Database Viewing

- `GET /dashboard/api/database/tables` - List all database tables
  - Returns: `{"tables": ["games", "players", "orders", ...]}`

- `GET /dashboard/api/database/table/{table_name}` - Get table data
  - Params: `table_name`, optional `limit` (default 100), optional `offset`
  - Returns paginated table data with schema info
  - **Security**: Read-only queries only, validate table names against whitelist

- `GET /dashboard/api/database/stats` - Database statistics
  - Returns: `{"total_games": ..., "total_players": ..., "active_games": ..., ...}`

### 2. Frontend Dashboard (`src/server/dashboard/`)

#### Directory Structure

```
src/server/dashboard/
├── index.html          # Main dashboard page
├── static/
│   ├── dashboard.css   # Styling
│   └── dashboard.js    # JavaScript for API calls and UI updates
```

#### Dashboard Sections

**Service Status Panel**

- Real-time status indicators for both services (green/red)
- Uptime information
- Quick restart buttons for each service
- Auto-refresh every 5-10 seconds

**Logs Viewer**

- Dropdown to select service (diplomacy/diplomacy-bot)
- Scrollable log output area
- Controls: line count selector, refresh button, auto-scroll toggle
- Timestamp formatting
- Filter/search input (client-side)

**Database Viewer**

- Table selector dropdown
- Data table with pagination
- Basic search/filter per table
- Shows row count and basic table schema info

**Database Statistics**

- Summary cards showing:
  - Total games
  - Active games
  - Total players
  - Recent activity

### 3. Static File Serving

Add to `src/server/api.py`:

- Mount static files: `app.mount("/dashboard/static", StaticFiles(directory="..."), name="dashboard-static")`
- Serve dashboard HTML: `@app.get("/dashboard")` returns HTML file

### 4. System Integration

#### Nginx Configuration Update

- Already configured to proxy port 80 → 8000
- Dashboard accessible at `http://<server>/dashboard`

#### Security Considerations

- No authentication (as requested)
- Database queries restricted to SELECT only
- Table name whitelist validation
- Service restart limited to `diplomacy` and `diplomacy-bot` services only
- Systemd commands executed with proper error handling

## Implementation Files

### New Files

- `src/server/dashboard/index.html`
- `src/server/dashboard/static/dashboard.css`
- `src/server/dashboard/static/dashboard.js`

### Modified Files

- `src/server/api.py` - Add dashboard routes and API endpoints
- Update `requirements.txt` if needed (likely no new dependencies)

## Technical Details

### Systemd Integration

- Use `subprocess.run()` with `systemctl` commands
- Handle permission checks (may need sudo, but service runs as diplomacy user)
- Parse `systemctl status` output for service information

### Log Retrieval

- Use `journalctl -u <service> --no-pager -n <lines>` via subprocess
- Format output with timestamps
- Handle large log outputs efficiently

### Database Queries

- Use existing `DatabaseService` methods where possible
- For generic table viewing, execute raw SELECT queries safely
- Implement pagination to avoid loading entire tables

## Testing Considerations

- Test service restart functionality in development
- Verify log streaming works correctly
- Ensure database queries are read-only
- Test with actual service logs and database content

## Future Enhancements (Not in Initial Implementation)

- Real-time log streaming with Server-Sent Events (SSE)
- Database query builder/editor
- Export logs to file
- Historical log storage
- Service health metrics/graphs