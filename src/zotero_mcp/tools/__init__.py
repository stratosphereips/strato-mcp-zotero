"""Shared utilities for MCP tool modules."""
from __future__ import annotations

import logging
import re

from zotero_mcp.zotero.client import ZoteroApiError

logger = logging.getLogger(__name__)

_HTTP_STATUS_RE = re.compile(r"HTTP\s+(\d{3})")


def sanitize_api_error(exc: ZoteroApiError) -> str:
    """Return a safe, client-facing error string for a ZoteroApiError."""
    logger.warning("Zotero API error: %s", exc)
    match = _HTTP_STATUS_RE.search(str(exc))
    if match:
        return f"Zotero API error ({match.group(1)})"
    return "Zotero API request failed"
