"""Browser integration for opening approved websites."""

import webbrowser
from urllib.parse import urlparse
from jarvis.config import config
from jarvis.tools.registry import registry, ToolParameter
from jarvis.utils.logger import logger


@registry.register(
    name="open_website",
    description="Open an approved website in the user's default Windows web browser.",
    parameters=[
        ToolParameter(
            name="url",
            type_=str,
            description="The full URL or web address to open (e.g. 'https://www.wikipedia.org' or 'python.org').",
            required=True,
        )
    ],
)
def open_website(url: str) -> str:
    """Validate and open user-requested website."""
    target_url = url.strip()

    # Prepend https:// if omitted
    if not target_url.startswith("http://") and not target_url.startswith("https://"):
        target_url = f"https://{target_url}"

    parsed = urlparse(target_url)
    domain = parsed.hostname or ""

    if not domain:
        return f"Invalid URL: '{url}'. Please provide a valid domain or web address."

    # Validate against allowed domains
    is_allowed = False
    for allowed in config.security.allowed_domains:
        if domain == allowed or domain.endswith(f".{allowed}"):
            is_allowed = True
            break

    if not is_allowed:
        allowed_list = ", ".join(config.security.allowed_domains)
        return (
            f"Blocked URL: Domain '{domain}' is not in the approved websites allowlist. "
            f"Approved domains: {allowed_list}."
        )

    try:
        logger.info(f"Opening approved website in browser: {target_url}")
        success = webbrowser.open(target_url)
        if success:
            return f"Successfully opened {target_url} in your default browser."
        return f"Browser launch triggered for {target_url}."
    except Exception as exc:
        return f"Failed to open browser for '{target_url}': {exc}"
