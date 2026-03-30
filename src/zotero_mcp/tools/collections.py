"""MCP tool definitions for Zotero collections."""
from __future__ import annotations

import json
import logging
from typing import Any

from zotero_mcp.tools import sanitize_api_error
from zotero_mcp.zotero.client import ZoteroApiError
from zotero_mcp.zotero.collections import (
    VALID_DIRECTIONS,
    VALID_SORT_FIELDS,
    get_collection,
    list_collections,
)

logger = logging.getLogger(__name__)


def _error(message: str) -> str:
    return json.dumps({"error": message})


def register_collection_tools(mcp: Any, get_client: Any) -> None:
    """Register all collection-related MCP tools."""

    @mcp.tool()
    def list_collections_tool(
        parent_collection_key: str = "",
        top_level_only: bool = False,
        limit: int = 25,
        start: int = 0,
        sort: str = "dateModified",
        direction: str = "desc",
    ) -> str:
        """List collections from the configured Zotero library."""
        if sort not in VALID_SORT_FIELDS:
            return _error(f"sort must be one of: {', '.join(sorted(VALID_SORT_FIELDS))}")
        if direction not in VALID_DIRECTIONS:
            return _error("direction must be 'asc' or 'desc'")
        try:
            result = list_collections(
                get_client(),
                parent_collection_key=parent_collection_key or None,
                top_level_only=top_level_only,
                limit=limit,
                start=start,
                sort=sort,
                direction=direction,
            )
            return json.dumps(result)
        except ZoteroApiError as exc:
            return _error(sanitize_api_error(exc))
        except Exception:
            logger.exception("Unexpected error in list_collections_tool")
            return _error("An internal error occurred. Check server logs for details.")

    @mcp.tool()
    def get_collection_tool(collection_key: str) -> str:
        """Retrieve a single Zotero collection by key."""
        if not collection_key.strip():
            return _error("collection_key must not be empty")
        try:
            return json.dumps(get_collection(get_client(), collection_key=collection_key))
        except ZoteroApiError as exc:
            return _error(sanitize_api_error(exc))
        except Exception:
            logger.exception("Unexpected error in get_collection_tool")
            return _error("An internal error occurred. Check server logs for details.")
