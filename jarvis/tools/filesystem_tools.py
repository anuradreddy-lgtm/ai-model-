"""Safe filename search within user-specified directories."""

from pathlib import Path
from datetime import datetime
from jarvis.tools.registry import registry, ToolParameter
from jarvis.utils.logger import logger


@registry.register(
    name="search_files",
    description="Search for files by filename inside a user-selected folder.",
    parameters=[
        ToolParameter(
            name="folder_path",
            type_=str,
            description="The folder directory to search inside (e.g., 'C:\\Users\\anura\\Documents').",
            required=True,
        ),
        ToolParameter(
            name="filename_query",
            type_=str,
            description="The search string or file extension to look for (e.g., 'report', '.pdf', 'notes').",
            required=True,
        ),
        ToolParameter(
            name="max_results",
            type_=int,
            description="Maximum number of search results to return (default is 10).",
            required=False,
            default=10,
        ),
    ],
)
def search_files(folder_path: str, filename_query: str, max_results: int = 10) -> str:
    """Safely search directory for matching filenames with depth limits."""
    path = Path(folder_path).expanduser().resolve()

    if not path.exists():
        return f"Error: Folder '{folder_path}' does not exist."
    if not path.is_dir():
        return f"Error: '{folder_path}' is a file, not a directory."

    # Avoid scanning the entire root C:\ drive
    if len(path.parts) <= 1:
        return "Search safety restriction: Searching the entire drive root is not permitted to prevent system slowdown. Please specify a subfolder (e.g., Documents, Desktop, Downloads)."

    query_lower = filename_query.strip().lower()
    matches = []

    try:
        # Bounded scan: stop at max_results or max scanned files (1000)
        scanned_count = 0
        for entry in path.rglob("*"):
            scanned_count += 1
            if scanned_count > 1500:
                break

            if entry.is_file() and query_lower in entry.name.lower():
                try:
                    stat = entry.stat()
                    size_kb = stat.st_size / 1024
                    mod_time = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
                    matches.append(f"- {entry.name} ({size_kb:.1f} KB, modified {mod_time})\n  Path: {entry}")
                except (PermissionError, OSError):
                    continue

                if len(matches) >= max_results:
                    break

        if not matches:
            return f"No files matching '{filename_query}' found in '{folder_path}' (scanned {scanned_count} items)."

        header = f"Found {len(matches)} matching file(s) in '{folder_path}':\n"
        return header + "\n".join(matches)

    except PermissionError:
        return f"Permission denied accessing folder '{folder_path}'."
    except Exception as exc:
        return f"Error during file search: {exc}"
