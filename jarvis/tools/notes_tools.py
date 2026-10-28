"""Dedicated notes manager for creating and reading notes safely."""

import re
from datetime import datetime
from jarvis.config import config
from jarvis.tools.registry import registry, ToolParameter
from jarvis.utils.logger import logger


def sanitize_filename(name: str) -> str:
    """Sanitize note title into a safe filename preventing path traversal."""
    cleaned = re.sub(r'[\\/*?:"<>|]', "", name).strip()
    cleaned = cleaned.replace("..", "").replace("/", "").replace("\\", "")
    return cleaned or "untitled_note"


@registry.register(
    name="create_note",
    description="Save a new note with a title and content into the dedicated JARVIS notes repository.",
    parameters=[
        ToolParameter(
            name="title",
            type_=str,
            description="The short title or subject of the note.",
            required=True,
        ),
        ToolParameter(
            name="content",
            type_=str,
            description="The body text or details to save.",
            required=True,
        ),
    ],
)
def create_note(title: str, content: str) -> str:
    """Save note to local file."""
    safe_title = sanitize_filename(title)
    file_path = config.notes_dir / f"{safe_title}.txt"

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    note_body = f"Title: {title}\nDate: {timestamp}\n\n{content}\n"

    try:
        file_path.write_text(note_body, encoding="utf-8")
        logger.info(f"Saved note to '{file_path}'.")
        return f"Successfully created note '{safe_title}'."
    except Exception as exc:
        return f"Failed to save note '{title}': {exc}"


@registry.register(
    name="read_note",
    description="Read the contents of an existing note by title from the JARVIS notes folder.",
    parameters=[
        ToolParameter(
            name="title",
            type_=str,
            description="The title of the note to retrieve.",
            required=True,
        )
    ],
)
def read_note(title: str) -> str:
    """Retrieve note contents."""
    safe_title = sanitize_filename(title)
    file_path = config.notes_dir / f"{safe_title}.txt"

    if not file_path.exists():
        # Try finding a case-insensitive match
        for f in config.notes_dir.glob("*.txt"):
            if f.stem.lower() == safe_title.lower():
                file_path = f
                break

    if not file_path.exists():
        return f"Note '{title}' was not found. Use 'list_notes' to see available notes."

    try:
        content = file_path.read_text(encoding="utf-8")
        return f"Contents of '{title}':\n{content}"
    except Exception as exc:
        return f"Failed to read note '{title}': {exc}"


@registry.register(
    name="list_notes",
    description="List all notes stored in the dedicated JARVIS notes folder.",
    parameters=[],
)
def list_notes() -> str:
    """List all saved notes."""
    try:
        notes = list(config.notes_dir.glob("*.txt"))
        if not notes:
            return "No notes currently saved in JARVIS notes repository."

        items = []
        for n in notes:
            stat = n.stat()
            mod_time = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
            items.append(f"- {n.stem} (updated {mod_time})")

        return f"Stored Notes ({len(items)} total):\n" + "\n".join(items)
    except Exception as exc:
        return f"Error listing notes: {exc}"
