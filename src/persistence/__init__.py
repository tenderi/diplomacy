"""Persistence layer: SQLAlchemy models (``database``) and the data-access
service (``database_service``). Moved out of ``engine`` in M6 so the engine
package stays pure rules-logic. All non-engine code goes through
``DatabaseService`` rather than touching ORM models directly.
"""
