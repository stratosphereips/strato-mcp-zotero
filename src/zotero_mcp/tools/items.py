"""MCP tool definitions for Zotero items."""
from __future__ import annotations

import json
import logging
from typing import Any

from zotero_mcp.tools import sanitize_api_error
from zotero_mcp.zotero.client import ZoteroApiError
from zotero_mcp.zotero.items import (
    VALID_DIRECTIONS,
    VALID_QMODES,
    VALID_SORT_FIELDS,
    create_item,
    delete_item,
    get_item,
    list_items,
    search_items,
    update_item,
)

logger = logging.getLogger(__name__)


def _error(message: str) -> str:
    return json.dumps({"error": message})


def _parse_json_object(value: str, *, argument_name: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{argument_name} must be valid JSON.") from exc

    if not isinstance(parsed, dict):
        raise ValueError(f"{argument_name} must decode to a JSON object.")

    return parsed


def register_item_tools(mcp: Any, get_client: Any) -> None:
    """Register all item-related MCP tools."""

    @mcp.tool()
    def list_items_tool(
        collection_key: str = "",
        top_level_only: bool = False,
        limit: int = 25,
        start: int = 0,
        sort: str = "dateModified",
        direction: str = "desc",
        item_type: str = "",
        tag: str = "",
        include_trashed: bool = False,
    ) -> str:
        """List items from the configured Zotero library."""
        if sort not in VALID_SORT_FIELDS:
            return _error(f"sort must be one of: {', '.join(sorted(VALID_SORT_FIELDS))}")
        if direction not in VALID_DIRECTIONS:
            return _error("direction must be 'asc' or 'desc'")
        try:
            result = list_items(
                get_client(),
                collection_key=collection_key or None,
                top_level_only=top_level_only,
                limit=limit,
                start=start,
                sort=sort,
                direction=direction,
                item_type=item_type or None,
                tag=tag or None,
                include_trashed=include_trashed,
            )
            return json.dumps(result)
        except ZoteroApiError as exc:
            return _error(sanitize_api_error(exc))
        except Exception:
            logger.exception("Unexpected error in list_items_tool")
            return _error("An internal error occurred. Check server logs for details.")

    @mcp.tool()
    def search_items_tool(
        query: str,
        collection_key: str = "",
        top_level_only: bool = False,
        limit: int = 25,
        start: int = 0,
        sort: str = "dateModified",
        direction: str = "desc",
        item_type: str = "",
        tag: str = "",
        qmode: str = "titleCreatorYear",
        include_trashed: bool = False,
    ) -> str:
        """Search items by Zotero quick-search query."""
        if not query.strip():
            return _error("query must not be empty")
        if sort not in VALID_SORT_FIELDS:
            return _error(f"sort must be one of: {', '.join(sorted(VALID_SORT_FIELDS))}")
        if direction not in VALID_DIRECTIONS:
            return _error("direction must be 'asc' or 'desc'")
        if qmode not in VALID_QMODES:
            return _error(f"qmode must be one of: {', '.join(sorted(VALID_QMODES))}")
        try:
            result = search_items(
                get_client(),
                query=query,
                collection_key=collection_key or None,
                top_level_only=top_level_only,
                limit=limit,
                start=start,
                sort=sort,
                direction=direction,
                item_type=item_type or None,
                tag=tag or None,
                qmode=qmode,
                include_trashed=include_trashed,
            )
            return json.dumps(result)
        except ZoteroApiError as exc:
            return _error(sanitize_api_error(exc))
        except Exception:
            logger.exception("Unexpected error in search_items_tool")
            return _error("An internal error occurred. Check server logs for details.")

    @mcp.tool()
    def get_item_tool(item_key: str) -> str:
        """Retrieve a single Zotero item by key."""
        if not item_key.strip():
            return _error("item_key must not be empty")
        try:
            return json.dumps(get_item(get_client(), item_key=item_key))
        except ZoteroApiError as exc:
            return _error(sanitize_api_error(exc))
        except Exception:
            logger.exception("Unexpected error in get_item_tool")
            return _error("An internal error occurred. Check server logs for details.")

    @mcp.tool()
    def create_item_tool(item_json: str, write_token: str = "") -> str:
        """Create a Zotero item from JSON object data."""
        try:
            item_data = _parse_json_object(item_json, argument_name="item_json")
        except ValueError as exc:
            return _error(str(exc))

        if not item_data.get("itemType"):
            return _error("item_json must include an itemType field")

        try:
            return json.dumps(
                create_item(
                    get_client(),
                    item_data=item_data,
                    write_token=write_token or None,
                )
            )
        except ZoteroApiError as exc:
            return _error(sanitize_api_error(exc))
        except Exception:
            logger.exception("Unexpected error in create_item_tool")
            return _error("An internal error occurred. Check server logs for details.")

    @mcp.tool()
    def update_item_tool(
        item_key: str,
        item_json: str,
        current_version: int = 0,
    ) -> str:
        """Update a Zotero item with partial JSON data."""
        if not item_key.strip():
            return _error("item_key must not be empty")
        try:
            item_data = _parse_json_object(item_json, argument_name="item_json")
        except ValueError as exc:
            return _error(str(exc))
        try:
            return json.dumps(
                update_item(
                    get_client(),
                    item_key=item_key,
                    item_data=item_data,
                    current_version=current_version or None,
                )
            )
        except ZoteroApiError as exc:
            return _error(sanitize_api_error(exc))
        except Exception:
            logger.exception("Unexpected error in update_item_tool")
            return _error("An internal error occurred. Check server logs for details.")

    @mcp.tool()
    def delete_item_tool(item_key: str, current_version: int = 0) -> str:
        """Delete a Zotero item by key."""
        if not item_key.strip():
            return _error("item_key must not be empty")
        try:
            return json.dumps(
                delete_item(
                    get_client(),
                    item_key=item_key,
                    current_version=current_version or None,
                )
            )
        except ZoteroApiError as exc:
            return _error(sanitize_api_error(exc))
        except Exception:
            logger.exception("Unexpected error in delete_item_tool")
            return _error("An internal error occurred. Check server logs for details.")
