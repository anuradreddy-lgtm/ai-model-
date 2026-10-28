"""Memory manager handling conversation persistence and user-approved facts."""

import sqlite3
from typing import Dict, List, Optional
from datetime import datetime
from jarvis.storage.db import get_db_connection
from jarvis.utils.logger import logger


class MemoryManager:
    """Provides CRUD operations for conversation logs and user facts with privacy controls."""

    def save_message(self, session_id: str, role: str, content: str) -> None:
        """Persist a conversation turn to SQLite."""
        try:
            with get_db_connection() as conn:
                conn.execute(
                    "INSERT INTO conversations (session_id, role, content) VALUES (?, ?, ?);",
                    (session_id, role, content),
                )
                conn.commit()
        except sqlite3.Error as exc:
            logger.error(f"Failed to persist message to SQLite: {exc}")

    def get_recent_history(self, session_id: Optional[str] = None, limit: int = 30) -> List[Dict[str, str]]:
        """Retrieve recent conversation history."""
        try:
            with get_db_connection() as conn:
                if session_id:
                    cursor = conn.execute(
                        "SELECT role, content FROM conversations WHERE session_id = ? ORDER BY id DESC LIMIT ?;",
                        (session_id, limit),
                    )
                else:
                    cursor = conn.execute(
                        "SELECT role, content FROM conversations ORDER BY id DESC LIMIT ?;",
                        (limit,),
                    )
                rows = cursor.fetchall()
                # Return in chronological order
                return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
        except sqlite3.Error as exc:
            logger.error(f"Failed to fetch conversation history: {exc}")
            return []

    def clear_history(self, session_id: Optional[str] = None) -> int:
        """Clear conversation logs from SQLite."""
        try:
            with get_db_connection() as conn:
                if session_id:
                    cursor = conn.execute("DELETE FROM conversations WHERE session_id = ?;", (session_id,))
                else:
                    cursor = conn.execute("DELETE FROM conversations;")
                conn.commit()
                deleted = cursor.rowcount
                logger.info(f"Cleared {deleted} conversation records.")
                return deleted
        except sqlite3.Error as exc:
            logger.error(f"Failed to clear conversation history: {exc}")
            return 0

    def save_fact(self, key: str, value: str, category: str = "general") -> bool:
        """Store or update a user-approved fact."""
        clean_key = key.strip().lower().replace(" ", "_")
        clean_val = value.strip()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        try:
            with get_db_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO memories (key, value, category, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET
                        value = excluded.value,
                        category = excluded.category,
                        updated_at = excluded.updated_at;
                    """,
                    (clean_key, clean_val, category, now, now),
                )
                conn.commit()
                logger.info(f"Stored user memory fact '{clean_key}'.")
                return True
        except sqlite3.Error as exc:
            logger.error(f"Failed to save user fact '{clean_key}': {exc}")
            return False

    def get_fact(self, key: str) -> Optional[str]:
        """Retrieve a specific fact by key."""
        clean_key = key.strip().lower().replace(" ", "_")
        try:
            with get_db_connection() as conn:
                cursor = conn.execute("SELECT value FROM memories WHERE key = ?;", (clean_key,))
                row = cursor.fetchone()
                return row["value"] if row else None
        except sqlite3.Error as exc:
            logger.error(f"Failed to read fact '{clean_key}': {exc}")
            return None

    def list_all_facts(self) -> List[Dict[str, str]]:
        """List all stored user facts for inspection."""
        try:
            with get_db_connection() as conn:
                cursor = conn.execute("SELECT id, key, value, category, updated_at FROM memories ORDER BY key ASC;")
                rows = cursor.fetchall()
                return [
                    {
                        "id": str(r["id"]),
                        "key": r["key"],
                        "value": r["value"],
                        "category": r["category"],
                        "updated_at": r["updated_at"],
                    }
                    for r in rows
                ]
        except sqlite3.Error as exc:
            logger.error(f"Failed to list user facts: {exc}")
            return []

    def delete_fact(self, key: str) -> bool:
        """Delete a stored memory fact."""
        clean_key = key.strip().lower().replace(" ", "_")
        try:
            with get_db_connection() as conn:
                cursor = conn.execute("DELETE FROM memories WHERE key = ?;", (clean_key,))
                conn.commit()
                deleted = cursor.rowcount > 0
                if deleted:
                    logger.info(f"Deleted user memory fact '{clean_key}'.")
                return deleted
        except sqlite3.Error as exc:
            logger.error(f"Failed to delete fact '{clean_key}': {exc}")
            return False

    def clear_all_facts(self) -> int:
        """Purge all user memories for privacy."""
        try:
            with get_db_connection() as conn:
                cursor = conn.execute("DELETE FROM memories;")
                conn.commit()
                deleted = cursor.rowcount
                logger.info("Purged all stored user memory facts.")
                return deleted
        except sqlite3.Error as exc:
            logger.error(f"Failed to purge user facts: {exc}")
            return 0

    def format_memories_for_prompt(self) -> str:
        """Format stored user facts for injection into system prompt."""
        facts = self.list_all_facts()
        if not facts:
            return ""

        lines = ["USER-APPROVED MEMORIES & PREFERENCES:"]
        for f in facts:
            lines.append(f"- {f['key'].replace('_', ' ').title()}: {f['value']}")
        return "\n".join(lines)


# Global singleton instance
memory_manager = MemoryManager()
