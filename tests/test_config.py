"""Unit tests for configuration and state definitions."""

from jarvis.config import JarvisConfig, get_default_data_dir
from jarvis.core.state import AssistantState


def test_default_config_paths():
    """Verify default data paths and directory existence."""
    cfg = JarvisConfig()
    assert cfg.data_dir.exists()
    assert cfg.notes_dir.exists()
    assert cfg.logs_dir.exists()
    assert cfg.db_path.name == "jarvis.db"


def test_assistant_states_have_properties():
    """Verify each state has distinct color and status message."""
    for state in AssistantState:
        assert state.color.startswith("#")
        assert len(state.color) == 7
        assert len(state.status_message) > 0


def test_security_defaults():
    """Ensure sensitive system tools require confirmation and apps are allowlisted."""
    cfg = JarvisConfig()
    assert cfg.security.require_confirmation_for_consequential is True
    assert "calc.exe" in cfg.security.allowed_apps
    assert "notepad.exe" in cfg.security.allowed_apps
