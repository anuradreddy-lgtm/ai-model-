"""SQLite connection and schema migrations."""

import sqlite3
from pathlib import Path
from jarvis.config import config
from jarvis.utils.logger import logger


def get_db_connection() -> sqlite3.Connection:
    """Create and return a configured SQLite connection."""
    conn = sqlite3.connect(str(config.db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db() -> None:
    """Initialize database tables for conversation history and user memories."""
    logger.info(f"Initializing SQLite database at: {config.db_path}")
    with get_db_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                role TEXT NOT NULL,
                content TEXT NOT NULL
            );
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                value TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)

        conn.execute("CREATE INDEX IF NOT EXISTS idx_conv_session ON conversations(session_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_key ON memories(key);")
        conn.commit()


# Auto-initialize database schema on module import
init_db()
