"""MCP tool definitions for Zotero item schema helpers."""
from __future__ import annotations

import json
import logging
from typing import Any

from zotero_mcp.tools import sanitize_api_error
from zotero_mcp.zotero.client import ZoteroApiError
from zotero_mcp.zotero.schema import get_item_template, list_item_types

logger = logging.getLogger(__name__)


def _error(message: str) -> str:
    return json.dumps({"error": message})


def register_schema_tools(mcp: Any, get_client: Any) -> None:
    """Register schema-related helper tools."""

    @mcp.tool()
    def list_item_types_tool(locale: str = "") -> str:
        """List Zotero item types, optionally localized."""
        try:
            item_types = list_item_types(get_client(), locale=locale or None)
            return json.dumps({"item_types": item_types, "count": len(item_types)})
        except ZoteroApiError as exc:
            return _error(sanitize_api_error(exc))
        except Exception:
            logger.exception("Unexpected error in list_item_types_tool")
            return _error("An internal error occurred. Check server logs for details.")

    @mcp.tool()
    def get_item_template_tool(item_type: str, locale: str = "") -> str:
        """Return a create-ready template for a specific Zotero item type."""
        if not item_type.strip():
            return _error("item_type must not be empty")
        try:
            return json.dumps(
                get_item_template(
                    get_client(),
                    item_type=item_type,
                    locale=locale or None,
                )
            )
        except ZoteroApiError as exc:
            return _error(sanitize_api_error(exc))
        except Exception:
            logger.exception("Unexpected error in get_item_template_tool")
            return _error("An internal error occurred. Check server logs for details.")
