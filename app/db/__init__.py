"""
Database package for DEV.to Analytics Platform
PostgreSQL 18 schema with pgvector support
"""

from .tables import metadata, get_all_tables
from .connection import get_engine, get_connection

__all__ = ['metadata', 'get_all_tables', 'get_engine', 'get_connection']
