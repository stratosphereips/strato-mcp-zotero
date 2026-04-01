"""Helpers for resolving Zotero group libraries by name or ID."""
from __future__ import annotations

from typing import Any

from zotero_mcp.zotero.client import ZoteroApiError, ZoteroClient, ScopedClient


def list_groups(client: ZoteroClient) -> list[dict[str, Any]]:
    """Return all groups the authenticated user can access, normalised for display."""
    raw = client.list_groups()
    result = []
    for group in raw:
        data = group.get("data") if isinstance(group.get("data"), dict) else group
        group_id = str(data.get("id") or group.get("id") or "")
        name = data.get("name", "")
        if group_id and name:
            result.append({"group_id": group_id, "name": name, "library_prefix": f"/groups/{group_id}"})
    return result


def resolve_library_prefix(client: ZoteroClient, library_spec: str) -> str:
    """Resolve a library specifier to a Zotero API prefix string.

    Accepts:
    - "" or "personal" → the user's personal library (/users/<userID>)
    - A numeric string  → treated as a group ID (/groups/<id>)
    - A name string     → fuzzy-matched against accessible groups
    """
    spec = library_spec.strip()

    if not spec or spec.lower() == "personal":
        user_id = client.get_user_id()
        return f"/users/{user_id}"

    if spec.isdigit():
        return f"/groups/{spec}"

    groups = list_groups(client)
    lowered = spec.lower()
    exact = [g for g in groups if g["name"].lower() == lowered]
    if len(exact) == 1:
        return exact[0]["library_prefix"]
    if len(exact) > 1:
        options = "; ".join(f"{g['name']} ({g['group_id']})" for g in exact[:5])
        raise ZoteroApiError(
            f"Multiple groups matched {spec!r}. Use a group ID to disambiguate: {options}"
        )

    fuzzy = [g for g in groups if lowered in g["name"].lower()]
    if len(fuzzy) == 1:
        return fuzzy[0]["library_prefix"]
    if len(fuzzy) > 1:
        options = "; ".join(f"{g['name']} ({g['group_id']})" for g in fuzzy[:5])
        raise ZoteroApiError(
            f"Multiple groups matched {spec!r}. Use a group ID or more specific name: {options}"
        )

    raise ZoteroApiError(
        f"No group matched {spec!r}. Use list_libraries to see available libraries."
    )


def scoped_client_for(client: ZoteroClient, library_spec: str) -> ScopedClient:
    """Return a ScopedClient targeting the resolved library."""
    prefix = resolve_library_prefix(client, library_spec)
    return ScopedClient(client, prefix)
