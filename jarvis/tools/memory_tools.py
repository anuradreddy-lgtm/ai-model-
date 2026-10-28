"""Tools for saving and recalling user-approved memories."""

from jarvis.tools.registry import registry, ToolParameter
from jarvis.storage.memory import memory_manager


@registry.register(
    name="remember_fact",
    description="Save a user-approved personal fact or preference (e.g. user name, favorite app, city) into local persistent SQLite memory.",
    parameters=[
        ToolParameter(
            name="key",
            type_=str,
            description="The short identifier or label of the fact (e.g. 'user_name', 'favorite_editor').",
            required=True,
        ),
        ToolParameter(
            name="value",
            type_=str,
            description="The fact or preference details to remember.",
            required=True,
        ),
    ],
)
def remember_fact(key: str, value: str) -> str:
    """Store fact in SQLite."""
    success = memory_manager.save_fact(key=key, value=value)
    if success:
        return f"Successfully remembered '{key}': {value}."
    return f"Failed to save memory for '{key}'."


@registry.register(
    name="recall_facts",
    description="Recall all stored user-approved memories and preferences from local SQLite memory.",
    parameters=[],
)
def recall_facts() -> str:
    """Retrieve stored facts."""
    facts = memory_manager.list_all_facts()
    if not facts:
        return "No stored memories found."

    items = [f"- {f['key']}: {f['value']}" for f in facts]
    return "Stored Memories:\n" + "\n".join(items)
