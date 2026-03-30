"""Workflow helpers for agent-friendly Zotero library operations."""
from __future__ import annotations

from typing import Any

from zotero_mcp.zotero.client import ZoteroApiError
from zotero_mcp.zotero.collections import get_collection, list_collections


def find_collection_by_name_or_key(client: Any, collection: str) -> dict[str, Any]:
    """Resolve a collection by key or by an exact/fuzzy name match."""
    candidate = collection.strip()
    if not candidate:
        raise ZoteroApiError("collection must not be empty")

    try:
        return get_collection(client, candidate)
    except ZoteroApiError as exc:
        if exc.status_code not in {None, 404}:
            raise

    lowered = candidate.lower()
    exact_matches: list[dict[str, Any]] = []
    fuzzy_matches: list[dict[str, Any]] = []
    start = 0

    for item in _iter_all_collections(client):
        name = _collection_name(item)
        if not name:
            continue
        if name.lower() == lowered:
            exact_matches.append(item)
        elif lowered in name.lower():
            fuzzy_matches.append(item)

    if len(exact_matches) == 1:
        return exact_matches[0]
    if len(exact_matches) > 1:
        raise ZoteroApiError(_ambiguous_collection_message(candidate, exact_matches))
    if len(fuzzy_matches) == 1:
        return fuzzy_matches[0]
    if len(fuzzy_matches) > 1:
        raise ZoteroApiError(_ambiguous_collection_message(candidate, fuzzy_matches))

    raise ZoteroApiError(
        f"No collection matched {candidate!r}. Provide an exact Zotero collection key "
        "or a more specific collection name."
    )


def resolve_collection_inputs(client: Any, collections: str) -> list[str]:
    """Resolve a comma-separated list of collection names or keys to keys."""
    tokens = [token.strip() for token in collections.split(",") if token.strip()]
    resolved: list[str] = []
    for token in tokens:
        collection = find_collection_by_name_or_key(client, token)
        key = collection.get("key") or collection.get("data", {}).get("key")
        if key:
            resolved.append(key)
    return resolved


def _iter_all_collections(client: Any) -> list[dict[str, Any]]:
    """Yield all collections by walking each parent recursively."""
    queue: list[str | None] = [None]
    while queue:
        parent = queue.pop(0)
        start = 0
        while True:
            page = list_collections(
                client,
                parent_collection_key=parent,
                limit=100,
                start=start,
                sort="title",
                direction="asc",
            )
            collections = page["items"]
            for item in collections:
                yield item
                key = item.get("key") or item.get("data", {}).get("key")
                if key:
                    queue.append(key)
            if len(collections) < 100:
                break
            start += 100


def summarize_item(item: dict[str, Any], *, include_raw: bool = False) -> dict[str, Any]:
    """Return a compact, agent-friendly view of a Zotero item."""
    data = item.get("data") if isinstance(item.get("data"), dict) else item
    result: dict[str, Any] = {
        "item_key": item.get("key") or data.get("key"),
        "item_type": data.get("itemType"),
        "title": _item_title(data),
        "creators": [_format_creator(creator) for creator in data.get("creators", [])],
        "date": data.get("date", ""),
        "year": _year_from_date(data.get("date", "")),
        "publication_title": _first_present(
            data,
            ["publicationTitle", "bookTitle", "websiteTitle", "proceedingsTitle"],
        ),
        "doi": data.get("DOI", ""),
        "url": data.get("url", ""),
        "abstract_note": _truncate(data.get("abstractNote", ""), 500),
        "tags": [tag.get("tag", "") for tag in data.get("tags", []) if tag.get("tag")],
        "collection_keys": list(data.get("collections", [])),
        "extra": data.get("extra", ""),
    }

    if include_raw:
        result["raw_item"] = item

    return result


def summarize_collection(collection: dict[str, Any]) -> dict[str, Any]:
    """Return a compact, agent-friendly view of a Zotero collection."""
    data = collection.get("data") if isinstance(collection.get("data"), dict) else collection
    meta = collection.get("meta") if isinstance(collection.get("meta"), dict) else {}
    return {
        "collection_key": collection.get("key") or data.get("key"),
        "name": data.get("name", ""),
        "parent_collection_key": data.get("parentCollection") or "",
        "num_items": meta.get("numItems"),
    }


def build_source_payload(
    *,
    item_type: str,
    title: str,
    creators: str = "",
    year: str = "",
    doi: str = "",
    url: str = "",
    abstract_note: str = "",
    publication_title: str = "",
    tags: str = "",
    collection_keys: list[str] | None = None,
    extra: str = "",
    extra_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a Zotero item payload from flat source-oriented fields."""
    payload: dict[str, Any] = {
        "itemType": item_type.strip(),
        "title": title.strip(),
    }

    if creators.strip():
        payload["creators"] = _parse_creators(creators)
    if year.strip():
        payload["date"] = year.strip()
    if doi.strip():
        payload["DOI"] = doi.strip()
    if url.strip():
        payload["url"] = url.strip()
    if abstract_note.strip():
        payload["abstractNote"] = abstract_note.strip()
    if publication_title.strip():
        payload["publicationTitle"] = publication_title.strip()
    if tags.strip():
        payload["tags"] = [{"tag": token} for token in _split_csv(tags)]
    if collection_keys:
        payload["collections"] = collection_keys
    if extra.strip():
        payload["extra"] = extra.strip()

    if extra_fields:
        payload.update(extra_fields)

    return payload


def build_source_changes(
    *,
    title: str = "",
    creators: str = "",
    year: str = "",
    doi: str = "",
    url: str = "",
    abstract_note: str = "",
    publication_title: str = "",
    tags: str = "",
    collection_keys: list[str] | None = None,
    extra: str = "",
    extra_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a Zotero patch payload from flat source-oriented fields."""
    changes: dict[str, Any] = {}

    if title.strip():
        changes["title"] = title.strip()
    if creators.strip():
        changes["creators"] = _parse_creators(creators)
    if year.strip():
        changes["date"] = year.strip()
    if doi.strip():
        changes["DOI"] = doi.strip()
    if url.strip():
        changes["url"] = url.strip()
    if abstract_note.strip():
        changes["abstractNote"] = abstract_note.strip()
    if publication_title.strip():
        changes["publicationTitle"] = publication_title.strip()
    if tags.strip():
        changes["tags"] = [{"tag": token} for token in _split_csv(tags)]
    if collection_keys:
        changes["collections"] = collection_keys
    if extra.strip():
        changes["extra"] = extra.strip()
    if extra_fields:
        changes.update(extra_fields)

    return changes


def _split_csv(value: str) -> list[str]:
    return [token.strip() for token in value.split(",") if token.strip()]


def _parse_creators(creators: str) -> list[dict[str, str]]:
    parsed: list[dict[str, str]] = []
    for entry in [token.strip() for token in creators.split(";") if token.strip()]:
        creator_type = "author"
        name_part = entry
        if ":" in entry:
            maybe_type, remainder = entry.split(":", 1)
            if remainder.strip():
                creator_type = maybe_type.strip() or creator_type
                name_part = remainder.strip()

        if "," in name_part:
            last_name, first_name = [piece.strip() for piece in name_part.split(",", 1)]
            parsed.append(
                {
                    "creatorType": creator_type,
                    "firstName": first_name,
                    "lastName": last_name,
                }
            )
            continue

        if " " in name_part:
            first_name, last_name = name_part.rsplit(" ", 1)
            parsed.append(
                {
                    "creatorType": creator_type,
                    "firstName": first_name.strip(),
                    "lastName": last_name.strip(),
                }
            )
            continue

        parsed.append({"creatorType": creator_type, "name": name_part})

    return parsed


def _item_title(data: dict[str, Any]) -> str:
    return _first_present(
        data,
        [
            "title",
            "shortTitle",
            "caseName",
            "subject",
            "name",
        ],
    )


def _collection_name(collection: dict[str, Any]) -> str:
    data = collection.get("data") if isinstance(collection.get("data"), dict) else collection
    return data.get("name", "")


def _first_present(data: dict[str, Any], fields: list[str]) -> str:
    for field in fields:
        value = data.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _format_creator(creator: dict[str, Any]) -> str:
    if creator.get("name"):
        return creator["name"]
    first = creator.get("firstName", "").strip()
    last = creator.get("lastName", "").strip()
    return " ".join(part for part in [first, last] if part)


def _year_from_date(date_value: str) -> str:
    date_value = date_value.strip()
    return date_value[:4] if len(date_value) >= 4 else date_value


def _truncate(value: str, limit: int) -> str:
    value = value.strip()
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."


def _ambiguous_collection_message(
    collection: str,
    matches: list[dict[str, Any]],
) -> str:
    options = []
    for match in matches[:5]:
        summary = summarize_collection(match)
        options.append(f"{summary['name']} ({summary['collection_key']})")
    joined = "; ".join(options)
    return (
        f"Multiple collections matched {collection!r}. "
        f"Use one of these collection keys instead: {joined}"
    )
