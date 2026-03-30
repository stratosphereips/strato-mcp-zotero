"""Zotero item API wrappers."""
from __future__ import annotations

import secrets
from typing import Any

from zotero_mcp.zotero.client import (
    ZoteroApiError,
    ZoteroClient,
    build_list_result,
    extract_version,
)

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
}
VALID_DIRECTIONS = {"asc", "desc"}
VALID_QMODES = {"titleCreatorYear", "everything"}


def list_items(
    client: ZoteroClient,
    *,
    collection_key: str | None = None,
    top_level_only: bool = False,
    limit: int = 25,
    start: int = 0,
    sort: str = "dateModified",
    direction: str = "desc",
    item_type: str | None = None,
    tag: str | None = None,
    include_trashed: bool = False,
) -> dict[str, Any]:
    """List items in the configured Zotero library."""
    path = _items_path(client, collection_key=collection_key, top_level_only=top_level_only)
    params = _item_list_params(
        limit=limit,
        start=start,
        sort=sort,
        direction=direction,
        item_type=item_type,
        tag=tag,
        include_trashed=include_trashed,
    )
    data, response = client.request_json("GET", path, params=params)
    return build_list_result(data, response, start=start, limit=params["limit"])


def search_items(
    client: ZoteroClient,
    *,
    query: str,
    collection_key: str | None = None,
    top_level_only: bool = False,
    limit: int = 25,
    start: int = 0,
    sort: str = "dateModified",
    direction: str = "desc",
    item_type: str | None = None,
    tag: str | None = None,
    qmode: str = "titleCreatorYear",
    include_trashed: bool = False,
) -> dict[str, Any]:
    """Search items in the configured Zotero library."""
    path = _items_path(client, collection_key=collection_key, top_level_only=top_level_only)
    params = _item_list_params(
        limit=limit,
        start=start,
        sort=sort,
        direction=direction,
        item_type=item_type,
        tag=tag,
        include_trashed=include_trashed,
    )
    params["q"] = query
    params["qmode"] = qmode
    data, response = client.request_json("GET", path, params=params)
    return build_list_result(data, response, start=start, limit=params["limit"])


def get_item(client: ZoteroClient, item_key: str) -> dict[str, Any]:
    """Retrieve a single item by key."""
    data, _ = client.request_json("GET", f"{client.get_library_prefix()}/items/{item_key}")
    return data


def create_item(
    client: ZoteroClient,
    item_data: dict[str, Any],
    *,
    write_token: str | None = None,
) -> dict[str, Any]:
    """Create a Zotero item."""
    headers = {"Zotero-Write-Token": write_token or secrets.token_hex(16)}
    data, response = client.request_json(
        "POST",
        f"{client.get_library_prefix()}/items",
        json_body=[item_data],
        headers=headers,
    )
    result = data if isinstance(data, dict) else {"result": data}
    if response.headers.get("Last-Modified-Version"):
        result["last_modified_version"] = response.headers["Last-Modified-Version"]
    return result


def update_item(
    client: ZoteroClient,
    item_key: str,
    item_data: dict[str, Any],
    *,
    current_version: int | None = None,
) -> dict[str, Any]:
    """Update a Zotero item using POST patch semantics."""
    if current_version is None:
        current_version = extract_version(get_item(client, item_key))
    if current_version is None:
        raise ZoteroApiError(
            f"Could not determine the current version for item {item_key!r}."
        )

    payload = dict(item_data)
    payload["key"] = item_key
    payload["version"] = current_version

    data, response = client.request_json(
        "POST",
        f"{client.get_library_prefix()}/items",
        json_body=[payload],
    )
    result = data if isinstance(data, dict) else {"result": data}
    if response.headers.get("Last-Modified-Version"):
        result["last_modified_version"] = response.headers["Last-Modified-Version"]
    return result


def delete_item(
    client: ZoteroClient,
    item_key: str,
    *,
    current_version: int | None = None,
) -> dict[str, Any]:
    """Delete a Zotero item by key."""
    if current_version is None:
        current_version = extract_version(get_item(client, item_key))
    if current_version is None:
        raise ZoteroApiError(
            f"Could not determine the current version for item {item_key!r}."
        )

    _, response = client.request_json(
        "DELETE",
        f"{client.get_library_prefix()}/items/{item_key}",
        headers={"If-Unmodified-Since-Version": str(current_version)},
    )
    result: dict[str, Any] = {
        "deleted": True,
        "item_key": item_key,
        "version": current_version,
    }
    if response.headers.get("Last-Modified-Version"):
        result["last_modified_version"] = response.headers["Last-Modified-Version"]
    return result


def _items_path(
    client: ZoteroClient,
    *,
    collection_key: str | None,
    top_level_only: bool,
) -> str:
    prefix = client.get_library_prefix()
    if collection_key:
        if top_level_only:
            return f"{prefix}/collections/{collection_key}/items/top"
        return f"{prefix}/collections/{collection_key}/items"
    if top_level_only:
        return f"{prefix}/items/top"
    return f"{prefix}/items"


def _item_list_params(
    *,
    limit: int,
    start: int,
    sort: str,
    direction: str,
    item_type: str | None,
    tag: str | None,
    include_trashed: bool,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "format": "json",
        "limit": min(max(1, limit), MAX_LIMIT),
        "start": max(0, start),
        "sort": sort,
        "direction": direction,
    }
    if item_type:
        params["itemType"] = item_type
    if tag:
        params["tag"] = tag
    if include_trashed:
        params["includeTrashed"] = 1
    return params
