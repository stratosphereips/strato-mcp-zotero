"""MCP server entry point for Zotero."""
from __future__ import annotations

import logging
import sys
import threading

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

SERVER_INSTRUCTIONS = """
This server helps an agent work with Zotero libraries as a research-source workspace.
It supports a personal library and multiple group libraries accessible with the configured API key.

Preferred workflow:
1. If the user mentions a group or library by name, call list_libraries first to resolve it.
2. Use find_library_sources to discover likely relevant saved sources in a specific library.
3. Use search_across_libraries when the user wants to check multiple libraries at once.
4. Use inspect_saved_source only after you already have an item key.
5. Use review_collection when the user asks about a collection by name.
6. Use write tools only when the user clearly wants to save or update a source.

Multi-library tips:
- All tools accept a "library" parameter: "personal", a group name, or a numeric group ID.
- When the library parameter is omitted, the default configured library is used.
- Group names are fuzzy-matched, so "Deception Research" will resolve automatically.
- Use search_across_libraries to fan out a single query across several libraries.

Notes:
- This server is intentionally curated around research-library workflows rather than raw Zotero endpoints.
- Read tools are safer defaults. Remove operations are destructive.
- If a collection name is ambiguous, ask the user or use the returned collection keys.
""".strip()

mcp = FastMCP("Zotero", instructions=SERVER_INSTRUCTIONS)

_client = None
_client_lock = threading.Lock()


def _get_client():
    with _client_lock:
        if _client is None:
            raise RuntimeError(
                "Zotero client not initialised. Ensure main() completed startup."
            )
        return _client


def _register_tools() -> None:
    from zotero_mcp.tools.library import register_library_tools

    register_library_tools(mcp, _get_client)


def main() -> None:
    """Entry point called by the pyproject.toml script."""
    global _client

    from zotero_mcp.config import ConfigurationError, load_config
    from zotero_mcp.zotero.client import ZoteroApiError, build_client

    try:
        config = load_config()
    except ConfigurationError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        client = build_client(config)
        client.get_user_id()  # Validates API key and resolves user ID eagerly
    except ZoteroApiError as exc:
        print(f"Zotero API error: {exc}", file=sys.stderr)
        sys.exit(1)

    with _client_lock:
        _client = client

    logger.info("Zotero client initialised successfully")
    _register_tools()
    mcp.run()


if __name__ == "__main__":
    main()
