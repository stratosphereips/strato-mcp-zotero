"""Workflow-first MCP tools for Zotero research libraries."""
from __future__ import annotations

import json
from typing import Any

from zotero_mcp.zotero.client import ZoteroApiError
from zotero_mcp.zotero.collections import list_collections
from zotero_mcp.zotero.groups import list_groups, scoped_client_for
from zotero_mcp.zotero.items import create_item, get_item, list_items, search_items, update_item
from zotero_mcp.zotero.library import (
    build_source_changes,
    build_source_payload,
    find_collection_by_name_or_key,
    resolve_collection_inputs,
    summarize_collection,
    summarize_item,
)

def _tool_annotations(*, read_only: bool, destructive: bool = False):
    try:
        from mcp.types import ToolAnnotations
    except ImportError:
        return None
    return ToolAnnotations(
        readOnlyHint=read_only,
        destructiveHint=destructive,
        idempotentHint=read_only and not destructive,
        openWorldHint=True,
    )


def _parse_json_object(value: str, *, argument_name: str) -> dict[str, Any]:
    if not value.strip():
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{argument_name} must be valid JSON. Example: {{\"language\": \"en\", \"place\": \"Prague\"}}"
        ) from exc

    if not isinstance(parsed, dict):
        raise ValueError(f"{argument_name} must decode to a JSON object.")

    return parsed


def _extract_created_key(result: dict[str, Any]) -> str | None:
    successful = result.get("successful")
    if not isinstance(successful, dict) or not successful:
        return None
    first_value = next(iter(successful.values()))
    if isinstance(first_value, str):
        return first_value
    if isinstance(first_value, dict):
        key = first_value.get("key")
        if isinstance(key, str):
            return key
    return None


def _library_label(library_spec: str) -> str:
    """Return a display name for a library specifier."""
    spec = library_spec.strip()
    if not spec or spec.lower() == "personal":
        return "personal library"
    return spec


def register_library_tools(mcp: Any, get_client: Any) -> None:
    """Register workflow-first Zotero tools."""

    @mcp.tool(
        name="list_libraries",
        annotations=_tool_annotations(read_only=True),
    )
    def list_libraries() -> dict[str, Any]:
        """List all Zotero libraries accessible with the configured API key.

        Returns the personal library and all group libraries the user belongs to,
        with their names and IDs. Use this tool first when the user refers to a
        library or group by name, so you can resolve the name before searching.

        Returns:
            personal: The user's personal library with its prefix.
            groups: A list of group libraries, each with group_id, name, and library_prefix.
        """
        client = get_client()
        user_id = client.get_user_id()
        groups = list_groups(client)
        return {
            "personal": {
                "library_prefix": f"/users/{user_id}",
                "description": "Your personal Zotero library",
            },
            "groups": groups,
        }

    @mcp.tool(
        name="find_library_sources",
        annotations=_tool_annotations(read_only=True),
    )
    def find_library_sources(
        query: str,
        library: str = "",
        limit: int = 8,
        collection: str = "",
        item_type: str = "",
        tag: str = "",
        include_trashed: bool = False,
    ) -> dict[str, Any]:
        """Find the most relevant saved sources for a topic, question, title fragment, DOI, or author.

        Use this as the default discovery tool when the user asks things like:
        - "find papers about retrieval-augmented generation"
        - "do I already have this DOI in Zotero?"
        - "show sources by Kahneman in my ML collection"
        - "find papers on deception in the 'Deception Research' group"

        Args:
            query: Search text to run against the Zotero library.
            library: Which library to search. Accepts "personal" (default), a group name
                     such as "Deception Research", or a numeric group ID. Leave empty to
                     use the default configured library.
            limit: Maximum number of matches to return. Strong default: 8.
            collection: Optional Zotero collection name or key to search inside.
            item_type: Optional Zotero item type such as 'book' or 'journalArticle'.
            tag: Optional Zotero tag filter.
            include_trashed: Include trashed items when true.

        Returns:
            A compact result with source summaries. Each summary contains:
            item_key, item_type, title, creators, year, publication_title, doi, url, tags.
        """
        if not query.strip():
            raise ValueError("query must not be empty")

        client = scoped_client_for(get_client(), library)
        collection_key = ""
        collection_summary = None
        if collection.strip():
            resolved_collection = find_collection_by_name_or_key(client, collection)
            collection_key = resolved_collection.get("key") or resolved_collection.get("data", {}).get("key", "")
            collection_summary = summarize_collection(resolved_collection)

        result = search_items(
            client,
            query=query.strip(),
            collection_key=collection_key or None,
            limit=limit,
            item_type=item_type.strip() or None,
            tag=tag.strip() or None,
            include_trashed=include_trashed,
        )
        return {
            "query": query.strip(),
            "library": _library_label(library),
            "collection": collection_summary,
            "count": result["count"],
            "sources": [summarize_item(item) for item in result["items"]],
        }

    @mcp.tool(
        name="search_across_libraries",
        annotations=_tool_annotations(read_only=True),
    )
    def search_across_libraries(
        query: str,
        libraries: str,
        limit: int = 8,
        item_type: str = "",
        tag: str = "",
    ) -> dict[str, Any]:
        """Search for sources across multiple Zotero libraries in one call.

        Use this when the user wants to check several libraries at once, e.g.:
        - "do I have any papers about bananas in 'Exotic Research' or my personal library?"
        - "search for 'LLM' across all my group libraries"

        Args:
            query: Search text to run against each library.
            libraries: Comma-separated list of library names to search. Use "personal" for
                       the personal library and group names or IDs for group libraries.
                       Example: "personal, Deception Research, Exotic Research"
            limit: Maximum results per library. Default: 8.
            item_type: Optional Zotero item type filter applied to all libraries.
            tag: Optional tag filter applied to all libraries.

        Returns:
            results: A dict keyed by library name, each containing count and sources.
            total_count: Total number of matches across all libraries.
        """
        if not query.strip():
            raise ValueError("query must not be empty")

        library_specs = [s.strip() for s in libraries.split(",") if s.strip()]
        if not library_specs:
            raise ValueError("libraries must contain at least one library name")

        base_client = get_client()
        results: dict[str, Any] = {}
        total_count = 0

        for spec in library_specs:
            label = _library_label(spec)
            try:
                client = scoped_client_for(base_client, spec)
                result = search_items(
                    client,
                    query=query.strip(),
                    limit=limit,
                    item_type=item_type.strip() or None,
                    tag=tag.strip() or None,
                )
                count = result["count"]
                total_count += count
                results[label] = {
                    "count": count,
                    "sources": [summarize_item(item) for item in result["items"]],
                }
            except ZoteroApiError as exc:
                results[label] = {"error": str(exc), "count": 0, "sources": []}

        return {
            "query": query.strip(),
            "total_count": total_count,
            "results": results,
        }

    @mcp.tool(
        name="inspect_saved_source",
        annotations=_tool_annotations(read_only=True),
    )
    def inspect_saved_source(
        item_key: str,
        library: str = "",
        include_raw: bool = False,
    ) -> dict[str, Any]:
        """Inspect one saved source by Zotero item key.

        Use this after you already know the item key and need details for answering a question,
        checking metadata, or preparing an update.

        Args:
            item_key: Zotero item key returned by another tool or known by the user.
            library: Which library the item belongs to. Accepts "personal" (default),
                     a group name, or a numeric group ID.
            include_raw: When true, also include the full raw Zotero item object.

        Returns:
            A normalized source summary. If include_raw=true, adds raw_item with the original API payload.
        """
        if not item_key.strip():
            raise ValueError("item_key must not be empty")
        client = scoped_client_for(get_client(), library)
        return summarize_item(get_item(client, item_key.strip()), include_raw=include_raw)

    @mcp.tool(
        name="review_collection",
        annotations=_tool_annotations(read_only=True),
    )
    def review_collection(
        collection: str,
        library: str = "",
        limit: int = 12,
        include_subcollections: bool = False,
    ) -> dict[str, Any]:
        """Review a Zotero collection and see its most useful contents in one step.

        Use this when the user asks:
        - "what is in my Reading Queue collection?"
        - "show the papers saved under Foundation Models"
        - "summarize this Zotero collection before we work on it"

        Args:
            collection: Zotero collection name or key.
            library: Which library to look in. Accepts "personal" (default),
                     a group name, or a numeric group ID.
            limit: Maximum number of item summaries to return from the collection.
            include_subcollections: Include direct child collections in the response.

        Returns:
            Collection metadata plus compact source summaries for the requested collection.
        """
        if not collection.strip():
            raise ValueError("collection must not be empty")

        client = scoped_client_for(get_client(), library)
        resolved = find_collection_by_name_or_key(client, collection)
        collection_key = resolved.get("key") or resolved.get("data", {}).get("key", "")
        items_result = list_items(client, collection_key=collection_key, limit=limit)

        response: dict[str, Any] = {
            "library": _library_label(library),
            "collection": summarize_collection(resolved),
            "source_count": items_result["count"],
            "sources": [summarize_item(item) for item in items_result["items"]],
        }

        if include_subcollections:
            child_result = list_collections(
                client,
                parent_collection_key=collection_key,
                limit=limit,
                sort="title",
                direction="asc",
            )
            response["subcollections"] = [
                summarize_collection(item) for item in child_result["items"]
            ]

        return response

    @mcp.tool(
        name="save_source_to_library",
        annotations=_tool_annotations(read_only=False),
    )
    def save_source_to_library(
        item_type: str,
        title: str,
        library: str = "",
        creators: str = "",
        year: str = "",
        doi: str = "",
        url: str = "",
        abstract_note: str = "",
        publication_title: str = "",
        tags: str = "",
        collections: str = "",
        extra: str = "",
        extra_fields_json: str = "",
    ) -> dict[str, Any]:
        """Save a new source to Zotero with flat, source-oriented arguments.

        Use this for common bibliographic saves such as books, articles, and webpages.
        Creator format: separate creators with ';'. Examples:
        - 'Ada Lovelace; Grace Hopper'
        - 'author: Turing, Alan; editor: Knuth, Donald'
        Collection format: comma-separated collection names or keys.
        Tags format: comma-separated tag names.

        Args:
            library: Which library to save into. Accepts "personal" (default),
                     a group name, or a numeric group ID.

        Returns:
            A confirmation plus a compact summary of the newly saved source when Zotero returns the new item key.
        """
        if not item_type.strip():
            raise ValueError("item_type must not be empty")
        if not title.strip():
            raise ValueError(
                "title must not be empty. For uncommon item types, call prepare_source_template first."
            )

        client = scoped_client_for(get_client(), library)
        extra_fields = _parse_json_object(
            extra_fields_json,
            argument_name="extra_fields_json",
        )
        collection_keys = resolve_collection_inputs(client, collections)
        payload = build_source_payload(
            item_type=item_type,
            title=title,
            creators=creators,
            year=year,
            doi=doi,
            url=url,
            abstract_note=abstract_note,
            publication_title=publication_title,
            tags=tags,
            collection_keys=collection_keys,
            extra=extra,
            extra_fields=extra_fields,
        )

        write_result = create_item(client, payload)
        created_key = _extract_created_key(write_result)

        response: dict[str, Any] = {
            "message": "Source saved to Zotero.",
            "library": _library_label(library),
            "write_result": write_result,
        }
        if created_key:
            response["source"] = summarize_item(get_item(client, created_key))
        else:
            response["submitted_payload"] = payload
        return response

    @mcp.tool(
        name="update_saved_source",
        annotations=_tool_annotations(read_only=False),
    )
    def update_saved_source(
        item_key: str,
        library: str = "",
        title: str = "",
        creators: str = "",
        year: str = "",
        doi: str = "",
        url: str = "",
        abstract_note: str = "",
        publication_title: str = "",
        tags: str = "",
        collections: str = "",
        extra: str = "",
        extra_fields_json: str = "",
        current_version: int = 0,
    ) -> dict[str, Any]:
        """Update a saved source with a small set of common metadata fields.

        Use this when the user says things like:
        - "fix the DOI on item ABCD1234"
        - "retitle this source"
        - "add tags and move it into the Reading Queue collection"

        Only provided fields are changed. Empty strings mean "leave as is".
        To update uncommon Zotero-specific fields, pass them in extra_fields_json.

        Args:
            library: Which library the item belongs to. Accepts "personal" (default),
                     a group name, or a numeric group ID.

        Returns:
            A confirmation plus an updated compact summary of the source.
        """
        if not item_key.strip():
            raise ValueError("item_key must not be empty")

        client = scoped_client_for(get_client(), library)
        extra_fields = _parse_json_object(
            extra_fields_json,
            argument_name="extra_fields_json",
        )
        collection_keys = resolve_collection_inputs(client, collections)
        changes = build_source_changes(
            title=title,
            creators=creators,
            year=year,
            doi=doi,
            url=url,
            abstract_note=abstract_note,
            publication_title=publication_title,
            tags=tags,
            collection_keys=collection_keys,
            extra=extra,
            extra_fields=extra_fields,
        )

        if not changes:
            raise ValueError(
                "Provide at least one field to change, such as title, year, doi, tags, "
                "collections, or extra_fields_json."
            )

        write_result = update_item(
            client,
            item_key=item_key.strip(),
            item_data=changes,
            current_version=current_version or None,
        )
        updated_item = get_item(client, item_key.strip())
        return {
            "message": "Source updated in Zotero.",
            "library": _library_label(library),
            "write_result": write_result,
            "source": summarize_item(updated_item),
        }
