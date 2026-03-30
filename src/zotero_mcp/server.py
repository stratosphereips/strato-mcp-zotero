"""MCP server entry point for Zotero."""
from __future__ import annotations

import logging
import sys
import threading

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

SERVER_INSTRUCTIONS = """
This server helps an agent work with a Zotero library as a research-source workspace.

Preferred workflow:
1. Use find_library_sources to discover likely relevant saved sources.
2. Use inspect_saved_source only after you already have an item key.
3. Use review_collection when the user asks about a collection by name.
4. Use write tools only when the user clearly wants to save or update a source.

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
        client.get_library_prefix()
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
