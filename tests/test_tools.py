"""Comprehensive unit and integration tests for safe Windows tool registry."""

import os
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from jarvis.config import config
from jarvis.tools.registry import ToolRegistry, ToolParameter, registry
from jarvis.tools.system_tools import get_current_time, get_hardware_status
from jarvis.tools.app_launcher import open_application
from jarvis.tools.browser_tools import open_website
from jarvis.tools.filesystem_tools import search_files
from jarvis.tools.notes_tools import create_note, read_note, list_notes, sanitize_filename


def test_registry_parameter_validation():
    """Verify registry enforces parameter types and required constraints."""
    reg = ToolRegistry()

    @reg.register(
        name="test_tool",
        description="A test tool",
        parameters=[
            ToolParameter(name="count", type_=int, description="Number of items", required=True),
            ToolParameter(name="tag", type_=str, description="Label", required=False, default="default"),
        ],
    )
    def my_handler(count: int, tag: str = "default") -> str:
        return f"{tag}:{count}"

    # Valid execution
    res = reg.execute("test_tool", {"count": "42", "tag": "custom"})
    assert res == "custom:42"

    # Missing required parameter
    res_err = reg.execute("test_tool", {"tag": "custom"})
    assert "Missing required parameter 'count'" in res_err

    # Invalid parameter type
    res_type_err = reg.execute("test_tool", {"count": "not-a-number"})
    assert "must be of type int" in res_type_err


def test_system_tools_time_and_hardware():
    """Verify get_current_time and get_hardware_status."""
    time_str = get_current_time()
    assert "Current time is" in time_str

    hw_str = get_hardware_status()
    assert "CPU Usage:" in hw_str
    assert "RAM:" in hw_str
    assert "Battery:" in hw_str


@patch("subprocess.Popen")
def test_app_launcher_allowed(mock_popen):
    """Verify allowlisted apps launch using argument list without shell=True."""
    mock_proc = MagicMock()
    mock_popen.return_value = mock_proc

    # Calculator
    res = open_application("calculator")
    assert "Successfully opened calc.exe" in res
    mock_popen.assert_called_with(["calc.exe"], close_fds=True)

    # Notepad
    res_np = open_application("notepad")
    assert "Successfully opened notepad.exe" in res_np
    mock_popen.assert_called_with(["notepad.exe"], close_fds=True)


def test_app_launcher_disallowed():
    """Verify unapproved applications are strictly denied."""
    res = open_application("ransomware.exe")
    assert "Access Denied" in res
    assert "not in the approved application allowlist" in res


@patch("webbrowser.open")
def test_browser_tools_allowed(mock_browser):
    """Verify approved domains open in default browser."""
    mock_browser.return_value = True

    res = open_website("https://www.wikipedia.org/wiki/Artificial_intelligence")
    assert "Successfully opened" in res
    mock_browser.assert_called_once()


def test_browser_tools_blocked():
    """Verify unapproved domains are blocked."""
    res = open_website("http://malicious-site.example.com")
    assert "Blocked URL" in res
    assert "not in the approved websites allowlist" in res


def test_filesystem_search(tmp_path):
    """Verify safe directory search and root directory restrictions."""
    # Test directory creation
    sub = tmp_path / "subdir"
    sub.mkdir()
    target_file = sub / "jarvis_project_plan.txt"
    target_file.write_text("Hello world", encoding="utf-8")

    # Search in tmp_path
    res = search_files(str(tmp_path), "jarvis_project")
    assert "jarvis_project_plan.txt" in res

    # Non-existent folder
    res_none = search_files(str(tmp_path / "does_not_exist"), "test")
    assert "does not exist" in res_none

    # Root drive safety guard
    res_root = search_files("C:\\", "test")
    assert "Search safety restriction" in res_root


def test_notes_tools(tmp_path, monkeypatch):
    """Verify note creation, reading, listing, and path traversal sanitization."""
    monkeypatch.setattr(config, "data_dir", tmp_path)

    # Path traversal title sanitization
    safe = sanitize_filename("../../../evil_path")
    assert ".." not in safe
    assert "/" not in safe
    assert "\\" not in safe

    # Create note
    create_res = create_note("Meeting Notes", "Discuss JARVIS architecture.")
    assert "Successfully created note 'Meeting Notes'" in create_res

    # List notes
    list_res = list_notes()
    assert "Meeting Notes" in list_res

    # Read note
    read_res = read_note("Meeting Notes")
    assert "Discuss JARVIS architecture." in read_res

    # Read missing note
    read_missing = read_note("Nonexistent")
    assert "was not found" in read_missing
