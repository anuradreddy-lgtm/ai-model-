"""Unit tests for SQLite database, memory manager, and privacy controls."""

import sqlite3
from pathlib import Path
import pytest
from jarvis.config import config
from jarvis.storage.memory import MemoryManager
from jarvis.storage.db import init_db, get_db_connection
from jarvis.tools.memory_tools import remember_fact, recall_facts


@pytest.fixture
def temp_memory_mgr(tmp_path, monkeypatch):
    """Provide an isolated MemoryManager backed by a temporary SQLite database."""
    test_db = tmp_path / "test_jarvis.db"
    monkeypatch.setattr(config, "data_dir", tmp_path)
    init_db()

    mgr = MemoryManager()
    return mgr


def test_save_and_retrieve_messages(temp_memory_mgr):
    """Verify conversation logging and retrieval in chronological order."""
    mgr = temp_memory_mgr
    session_id = "test_session_01"

    mgr.save_message(session_id, "user", "What is my schedule?")
    mgr.save_message(session_id, "assistant", "You have no events scheduled.")

    history = mgr.get_recent_history(session_id=session_id)
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "What is my schedule?"
    assert history[1]["role"] == "assistant"
    assert history[1]["content"] == "You have no events scheduled."


def test_clear_conversation_history(temp_memory_mgr):
    """Verify conversation clearing."""
    mgr = temp_memory_mgr
    session_id = "test_session_02"

    mgr.save_message(session_id, "user", "Hi")
    assert len(mgr.get_recent_history(session_id)) == 1

    cleared = mgr.clear_history(session_id)
    assert cleared == 1
    assert len(mgr.get_recent_history(session_id)) == 0


def test_fact_storage_crud(temp_memory_mgr):
    """Verify CRUD lifecycle for user-approved memories."""
    mgr = temp_memory_mgr

    # Save
    saved = mgr.save_fact("favorite_color", "Cyan", category="preference")
    assert saved is True

    # Read
    val = mgr.get_fact("favorite_color")
    assert val == "Cyan"

    # Update
    mgr.save_fact("favorite_color", "Electric Blue", category="preference")
    val_updated = mgr.get_fact("favorite_color")
    assert val_updated == "Electric Blue"

    # List
    all_facts = mgr.list_all_facts()
    assert len(all_facts) == 1
    assert all_facts[0]["key"] == "favorite_color"

    # Format for prompt
    prompt_snippet = mgr.format_memories_for_prompt()
    assert "Favorite Color: Electric Blue" in prompt_snippet

    # Delete
    deleted = mgr.delete_fact("favorite_color")
    assert deleted is True
    assert mgr.get_fact("favorite_color") is None

    # Clear all
    mgr.save_fact("city", "Seattle")
    mgr.save_fact("hobby", "Robotics")
    assert len(mgr.list_all_facts()) == 2
    purged = mgr.clear_all_facts()
    assert purged == 2
    assert len(mgr.list_all_facts()) == 0


def test_memory_tools_integration(temp_memory_mgr, monkeypatch):
    """Verify remember_fact and recall_facts tools."""
    monkeypatch.setattr("jarvis.tools.memory_tools.memory_manager", temp_memory_mgr)

    rem_res = remember_fact("username", "Anurag")
    assert "Successfully remembered" in rem_res

    recall_res = recall_facts()
    assert "username: Anurag" in recall_res
