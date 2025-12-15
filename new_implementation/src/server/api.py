"""
RESTful API server for Diplomacy game management and integration (e.g., Telegram bot).

This module provides the main FastAPI application and registers all route modules.
Route modules are organized by functionality:
- games: Game management endpoints
- orders: Order submission and retrieval
- users: User registration and session management
- messages: Private and broadcast messaging
- maps: Map image generation
- admin: Administrative endpoints
- dashboard: Dashboard API endpoints
"""
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from typing import Dict, Any
import contextlib
from contextlib import asynccontextmanager
import asyncio
import logging
from pathlib import Path

from .db_config import SQLALCHEMY_DATABASE_URL
from .api.shared import deadline_scheduler, db_service

# Import route modules
from .api.routes import games, orders, users, messages, maps, admin, dashboard, channels, health

# Set up logger
logger = logging.getLogger("diplomacy.server.api")

# --- Database Schema Initialization ---
def _initialize_database_schema():
    """Initialize database schema if it doesn't exist. Can be called synchronously.
    
    This function:
    - Checks if the database schema (tables) exists
    - Creates the schema if it doesn't exist
    - Logs errors but doesn't crash the server (endpoints will handle gracefully)
    """
    try:
        from engine.database import create_database_schema
        from sqlalchemy import create_engine, inspect
        from sqlalchemy.exc import OperationalError, ProgrammingError
        
        db_url = SQLALCHEMY_DATABASE_URL
        if not db_url:
            logging.warning("SQLALCHEMY_DATABASE_URL not set. Database-dependent endpoints will fail.")
            return
        
        try:
            engine = create_engine(db_url)
            try:
                inspector = inspect(engine)
                tables = inspector.get_table_names()
                
                needs_schema_create = 'games' not in tables
                needs_column_update = False
                
                if 'users' in tables:
                    # Check if users table has all required columns
                    users_columns = [col['name'] for col in inspector.get_columns('users')]
                    required_columns = ['is_active', 'created_at', 'updated_at']
                    missing_columns = [col for col in required_columns if col not in users_columns]
                    if missing_columns:
                        needs_column_update = True
                        logging.info(f"Users table missing columns: {missing_columns}, updating schema...")
                
                if 'games' in tables:
                    # Check if games table has channel columns
                    games_columns = [col['name'] for col in inspector.get_columns('games')]
                    required_channel_columns = ['channel_id', 'channel_settings']
                    missing_channel_columns = [col for col in required_channel_columns if col not in games_columns]
                    if missing_channel_columns:
                        needs_column_update = True
                        logging.info(f"Games table missing channel columns: {missing_channel_columns}, updating schema...")
                
                if needs_schema_create or needs_column_update:
                    if needs_column_update:
                        logging.info("Database schema missing columns, updating schema on startup...")
                    else:
                        logging.info("Database schema not found, creating schema on startup...")
                    try:
                        schema_engine = create_database_schema(db_url)
                        schema_engine.dispose()
                        # Verify with a fresh connection
                        verify_engine = create_engine(db_url)
                        verify_inspector = inspect(verify_engine)
                        verify_tables = verify_inspector.get_table_names()
                        verify_engine.dispose()
                        if 'games' in verify_tables:
                            logging.info("✅ Database schema initialized/updated successfully")
                        else:
                            logging.error("❌ Schema creation reported success but verification failed - tables still missing")
                    except Exception as schema_error:
                        logging.error(f"❌ Failed to create database schema: {schema_error}")
                        logging.error(f"   Database URL: {db_url.split('@')[1] if '@' in db_url else 'hidden'}")
                        raise
                else:
                    logging.info("✅ Database schema already exists")
            except (OperationalError, ProgrammingError) as db_error:
                logging.error(f"❌ Database connection error during schema check: {db_error}")
                logging.error(f"   Database URL: {db_url.split('@')[1] if '@' in db_url else 'hidden'}")
                logging.error("   Check that PostgreSQL is running and the database URL is correct")
            except Exception as e:
                logging.error(f"❌ Unexpected error checking database schema: {e}")
                import traceback
                logging.error(traceback.format_exc())
            finally:
                engine.dispose()
        except Exception as engine_error:
            logging.error(f"❌ Failed to create database engine: {engine_error}")
            logging.error(f"   Database URL: {db_url.split('@')[1] if '@' in db_url else 'hidden'}")
    except ImportError as import_error:
        logging.error(f"❌ Failed to import database modules: {import_error}")
        logging.error("   Ensure engine.database module is available")
    except Exception as e:
        # If schema initialization fails, log but don't crash - let endpoints handle it gracefully
        logging.error(f"❌ Database schema initialization failed: {e}")
        import traceback
        logging.error(traceback.format_exc())


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager.
    Starts the deadline_scheduler background task on app startup and ensures clean shutdown.
    Also ensures database schema is initialized before handling requests.
    """
    # Initialize database schema on startup (synchronous operation)
    _initialize_database_schema()
    
    task = asyncio.create_task(deadline_scheduler())
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

# Initialize schema immediately when module is imported (for TestClient compatibility)
# TestClient doesn't always trigger lifespan, so initialize here as well
_initialize_database_schema()

app = FastAPI(title="Diplomacy Server API", version="2.0.0", lifespan=lifespan)

# Register all route modules
app.include_router(games.router)
app.include_router(orders.router)
app.include_router(users.router)
app.include_router(messages.router)
app.include_router(maps.router)
app.include_router(admin.router)
app.include_router(dashboard.router)
app.include_router(channels.router, tags=["channels"])
app.include_router(health.router, tags=["health"])

# --- Core System Endpoints ---
@app.get("/scheduler/status")
def scheduler_status() -> Dict[str, Any]:
    """
    Simple endpoint to verify that the API is running and the scheduler is active.
    """
    return {"status": "ok", "scheduler": {"status": "running", "mode": "lifespan"}}

@app.get("/healthz")
def healthz() -> Dict[str, str]:
    """Kubernetes-style liveness probe."""
    try:
        db_service.execute_query('SELECT 1')
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {e}")

@app.get("/health")
def health_check() -> Dict[str, str]:
    try:
        db_service.execute_query('SELECT 1')
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {e}")

@app.get("/version")
def version() -> Dict[str, str]:
    """Simple version endpoint for diagnostics."""
    try:
        return {"version": app.version}
    except Exception:
        # Fallback if app.version is not set
        return {"version": "unknown"}

# --- Dashboard Frontend Serving ---
_dashboard_dir = Path(__file__).parent / "dashboard"
_static_dir = _dashboard_dir / "static"

# Mount static files if directory exists
if _static_dir.exists():
    app.mount("/dashboard/static", StaticFiles(directory=str(_static_dir)), name="dashboard-static")

@app.get("/", response_class=HTMLResponse)
def root() -> HTMLResponse:
    """Root endpoint - redirect to dashboard or show info."""
    dashboard_html = _dashboard_dir / "index.html"
    if dashboard_html.exists():
        return RedirectResponse(url="/dashboard")
    else:
        # Show API info if dashboard not available
        return HTMLResponse(
            content="""
            <html>
            <head><title>Diplomacy API</title></head>
            <body>
                <h1>Diplomacy Game Server API</h1>
                <p>API is running. Available endpoints:</p>
                <ul>
                    <li><a href="/docs">API Documentation (Swagger)</a></li>
                    <li><a href="/health">Health Check</a></li>
                    <li><a href="/dashboard">Dashboard</a> (if deployed)</li>
                </ul>
            </body>
            </html>
            """,
            status_code=200
        )

@app.get("/dashboard", response_class=HTMLResponse)
def serve_dashboard() -> HTMLResponse:
    """Serve the dashboard HTML page."""
    dashboard_html = _dashboard_dir / "index.html"
    if dashboard_html.exists():
        with open(dashboard_html, "r", encoding="utf-8") as f:
            content = f.read()
        return HTMLResponse(content=content)
    else:
        return HTMLResponse(
            content="<h1>Dashboard not found</h1><p>Dashboard files not installed.</p><p>Run <code>./deploy_dashboard.sh</code> to deploy the dashboard.</p>",
            status_code=404
        )

if __name__ == "__main__":
    import uvicorn
    # Note: Import path is server.api_module:app to avoid conflict with server.api package
    # For uvicorn CLI, use: uvicorn server.api_module:app
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
