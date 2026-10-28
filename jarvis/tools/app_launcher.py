"""Safe application launcher using allowlisted subprocess execution."""

import subprocess
import os
from typing import Dict
from jarvis.config import config
from jarvis.tools.registry import registry, ToolParameter
from jarvis.utils.logger import logger


APP_ALIASES: Dict[str, str] = {
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "notepad": "notepad.exe",
    "notes": "notepad.exe",
    "editor": "notepad.exe",
    "paint": "mspaint.exe",
    "mspaint": "mspaint.exe",
    "explorer": "explorer.exe",
    "files": "explorer.exe",
    "file explorer": "explorer.exe",
    "task manager": "taskmgr.exe",
    "taskmgr": "taskmgr.exe",
    "command prompt": "cmd.exe",
    "cmd": "cmd.exe",
}


@registry.register(
    name="open_application",
    description="Launch an approved Windows desktop application such as Calculator, Notepad, Paint, Explorer, or Task Manager.",
    parameters=[
        ToolParameter(
            name="app_name",
            type_=str,
            description="The name or alias of the application to open (e.g., 'calculator', 'notepad').",
            required=True,
        )
    ],
)
def open_application(app_name: str) -> str:
    """Safely open an allowlisted application using subprocess argument list."""
    clean_name = app_name.strip().lower()

    # Resolve alias or keep name
    target_exe = APP_ALIASES.get(clean_name, clean_name)
    if not target_exe.endswith(".exe"):
        target_exe = f"{target_exe}.exe"

    # Enforce strict allowlist check
    if target_exe not in config.security.allowed_apps:
        allowed = ", ".join(config.security.allowed_apps)
        return (
            f"Access Denied: Application '{app_name}' ('{target_exe}') is not in the approved application allowlist. "
            f"Allowed apps: {allowed}."
        )

    try:
        # Launch safely using argument list, NO shell=True
        logger.info(f"Launching allowed application: {target_exe}")
        subprocess.Popen([target_exe], close_fds=True)
        return f"Successfully opened {target_exe}."
    except FileNotFoundError:
        return f"Error: Application '{target_exe}' was not found on this Windows system."
    except Exception as exc:
        return f"Error launching '{target_exe}': {exc}"
