"""Zotero collection API wrappers."""
from __future__ import annotations

from typing import Any

from zotero_mcp.zotero.client import ZoteroClient, build_list_result

MAX_LIMIT = 100
VALID_SORT_FIELDS = {
    "dateAdded",
    "dateModified",
    "title",
    "creator",
    "itemType",
    "date",
    "publisher",
    "publicationTitle",
    "journalAbbreviation",
    "language",
    "accessDate",
    "libraryCatalog",
    "callNumber",
    "rights",
    "addedBy",
    "numItems",
}
VALID_DIRECTIONS = {"asc", "desc"}


def list_collections(
    client: ZoteroClient,
    *,
    parent_collection_key: str | None = None,
    top_level_only: bool = False,
    limit: int = 25,
    start: int = 0,
    sort: str = "dateModified",
    direction: str = "desc",
) -> dict[str, Any]:
    """List collections in the configured library."""
    prefix = client.get_library_prefix()
    if parent_collection_key:
        path = f"{prefix}/collections/{parent_collection_key}/collections"
    elif top_level_only:
        path = f"{prefix}/collections/top"
    else:
        path = f"{prefix}/collections"

    params = {
        "format": "json",
        "limit": min(max(1, limit), MAX_LIMIT),
        "start": max(0, start),
        "sort": sort,
        "direction": direction,
    }
    data, response = client.request_json("GET", path, params=params)
    return build_list_result(data, response, start=start, limit=params["limit"])


def get_collection(client: ZoteroClient, collection_key: str) -> dict[str, Any]:
    """Retrieve a single collection by key."""
    data, _ = client.request_json(
        "GET",
        f"{client.get_library_prefix()}/collections/{collection_key}",
    )
    return data
