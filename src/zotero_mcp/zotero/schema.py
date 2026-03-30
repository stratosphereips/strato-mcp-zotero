"""Zotero schema and template helpers."""
from __future__ import annotations

from typing import Any

from zotero_mcp.zotero.client import ZoteroClient


def list_item_types(client: ZoteroClient, *, locale: str | None = None) -> list[dict[str, Any]]:
    """Return available Zotero item types."""
    params = {"format": "json"}
    if locale:
        params["locale"] = locale
    data, _ = client.request_json("GET", "/itemTypes", params=params)
    return data


def get_item_template(
    client: ZoteroClient,
    item_type: str,
    *,
    locale: str | None = None,
) -> dict[str, Any]:
    """Return a template object suitable for creating a new item."""
    params = {
        "format": "json",
        "itemType": item_type,
    }
    if locale:
        params["locale"] = locale
    data, _ = client.request_json("GET", "/items/new", params=params)
    return data
