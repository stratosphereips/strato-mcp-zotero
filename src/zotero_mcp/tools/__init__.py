"""Shared utilities for MCP tool modules."""
from __future__ import annotations

import logging

from zotero_mcp.zotero.client import ZoteroApiError

logger = logging.getLogger(__name__)


_STATUS_GUIDANCE: dict[int, str] = {
    400: (
        "The request was malformed (HTTP 400). "
        "Check the parameters and correct them before retrying."
    ),
    401: (
        "Authentication failed (HTTP 401). "
        "The ZOTERO_API_KEY in .env is missing or invalid. "
        "Do not retry — ask the user to verify their API key."
    ),
    403: (
        "Access denied (HTTP 403). "
        "The configured API key does not have permission to access this library. "
        "Do not retry — ask the user to check the key's permissions in their Zotero account settings."
    ),
    404: (
        "Not found (HTTP 404). "
        "The item or collection does not exist in the library configured in .env "
        "(ZOTERO_LIBRARY_TYPE / ZOTERO_LIBRARY_ID). "
        "Do not retry — inform the user that this resource is not present in their configured library."
    ),
    409: (
        "Conflict (HTTP 409). "
        "The target collection does not exist in the library. "
        "Do not retry — ask the user to verify the collection key or name."
    ),
    412: (
        "Version conflict (HTTP 412). "
        "The item was modified since it was last fetched. "
        "Retrieve the item again to get the current version, then retry the update."
    ),
    429: (
        "Rate limited (HTTP 429). "
        "Too many requests to the Zotero API. "
        "Wait before retrying — do not immediately re-issue the same request."
    ),
}


def sanitize_api_error(exc: ZoteroApiError) -> str:
    """Return a client-facing error string with actionable guidance for the agent."""
    logger.warning("Zotero API error: %s", exc)
    status = exc.status_code
    if status in _STATUS_GUIDANCE:
        return _STATUS_GUIDANCE[status]
    if status is not None and status >= 500:
        return (
            f"Zotero server error (HTTP {status}). "
            "This is a temporary server-side issue. You may retry once after a short wait."
        )
    return f"Zotero API request failed (HTTP {status})." if status else "Zotero API request failed."
