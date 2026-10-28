"""Unit tests for conversation context bounds, state, and action parsing."""

from unittest.mock import MagicMock
from jarvis.conversation.manager import ConversationManager
from jarvis.core.state import AssistantState


def test_history_bounding():
    """Verify that conversation history is bounded by configured limits."""
    manager = ConversationManager()
    manager.reset_conversation()

    # Add 40 turns
    for i in range(40):
        manager.add_message("user", f"Question {i}")
        manager.add_message("assistant", f"Answer {i}")

    # Maximum turns is config.ollama.max_context_turns (12 * 2 = 24 messages)
    assert len(manager.history) == 24
    assert manager.history[-1]["content"] == "Answer 39"


def test_parse_action_block():
    """Verify JSON tool action parsing."""
    manager = ConversationManager()

    # Valid action block
    text = 'Let me open that for you.\nACTION: {"tool": "open_app", "args": {"app_name": "notepad"}}\nHave a nice day!'
    action = manager.parse_action_block(text)
    assert action is not None
    tool_name, tool_args = action
    assert tool_name == "open_app"
    assert tool_args == {"app_name": "notepad"}

    # No action block
    normal_text = "Hello! How can I help you today?"
    assert manager.parse_action_block(normal_text) is None


def test_state_transitions():
    """Verify state transitions and reset."""
    manager = ConversationManager()
    manager.set_state(AssistantState.LISTENING)
    assert manager.current_state == AssistantState.LISTENING

    manager.set_state(AssistantState.THINKING)
    assert manager.current_state == AssistantState.THINKING


def test_clean_final_response():
    """Verify that action blocks and internal markers are stripped from the final user-facing response."""
    manager = ConversationManager()

    # Raw response with action block prepended
    raw = 'ACTION: {"tool": "get_current_time", "args": {}}\nThe current time is 1:00 PM.'
    cleaned = manager.clean_final_response(raw)
    assert cleaned == "The current time is 1:00 PM."
    assert "ACTION:" not in cleaned

    # Normal response without actions
    normal = "Good afternoon! How can I help you?"
    assert manager.clean_final_response(normal) == normal


def test_tool_calling_only_returns_final_response():
    """Verify that when a tool is triggered, the final response is returned without raw action JSON."""
    manager = ConversationManager()
    manager.ollama = MagicMock()

    # Mock Pass 1: Model requests action
    # Mock Pass 2: Model summarizes tool result
    manager.ollama.chat_stream.side_effect = [
        'ACTION: {"tool": "get_current_time", "args": {}}',
        "The current time is 1:05 PM.",
    ]
    manager.ollama.ensure_model_available.return_value = "gemma4:e2b"

    reply = manager.process_user_input("What time is it?")
    assert reply == "The current time is 1:05 PM."
    assert "ACTION:" not in reply
