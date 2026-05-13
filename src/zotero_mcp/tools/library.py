"""Workflow-first MCP tools for Zotero research libraries."""
from __future__ import annotations

import json
from typing import Any

from zotero_mcp.zotero.client import ZoteroApiError, extract_version
from zotero_mcp.zotero.collections import list_collections
from zotero_mcp.zotero.groups import list_groups, scoped_client_for
from zotero_mcp.zotero.items import create_item, get_item, list_item_children, list_items, search_items, update_item
from zotero_mcp.zotero.library import (
    build_source_changes,
    build_source_payload,
    compute_tag_delta,
    find_collection_by_name_or_key,
    resolve_collection_inputs,
    split_csv,
    summarize_collection,
    summarize_item,
    tag_lists_equal,
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


_CITATION_KEY_PREFIX = "Citation Key: "


def _normalize_citation_key(value: str) -> str:
    """Strip whitespace and the BBT 'Citation Key: ' prefix if present."""
    key = value.strip()
    if key.startswith(_CITATION_KEY_PREFIX):
        key = key[len(_CITATION_KEY_PREFIX):].strip()
    return key


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
        name="get_library_item_count",
        annotations=_tool_annotations(read_only=True),
    )
    def get_library_item_count(
        library: str = "",
        include_attachments_and_notes: bool = False,
    ) -> dict[str, Any]:
        """Return the total number of items saved in a Zotero library.

        By default counts only parent (top-level) items — papers, books, webpages, etc. —
        excluding PDFs, notes, and other child attachments. Set
        include_attachments_and_notes=true to count everything.

        Use this when the user asks things like:
        - "how many items are in my library?"
        - "how large is the Deception Research group library?"
        - "what's the total item count in my personal Zotero?"

        Args:
            library: Which library to count. Accepts "personal" (default),
                     a group name such as "Deception Research", or a numeric
                     group ID. Leave empty to use the default configured library.
            include_attachments_and_notes: When true, count all items including
                     PDFs, notes, and other child attachments. Default: false.

        Returns:
            library: Display name of the queried library.
            total_items: Number of items counted.
            includes_attachments_and_notes: Whether the count includes child attachments and notes.
        """
        client = scoped_client_for(get_client(), library)
        top_level_only = not include_attachments_and_notes
        result = list_items(client, limit=1, top_level_only=top_level_only)
        return {
            "library": _library_label(library),
            "total_items": result.get("total_results", result["count"]),
            "includes_attachments_and_notes": include_attachments_and_notes,
        }

    @mcp.tool(
        name="find_library_sources",
        annotations=_tool_annotations(read_only=True),
    )
    def find_library_sources(
        query: str,
        library: str = "",
        limit: int = 8,
        offset: int = 0,
        collection: str = "",
        item_type: str = "",
        tag: str = "",
        citation_key: str = "",
        include_trashed: bool = False,
    ) -> dict[str, Any]:
        """Find the most relevant saved sources for a topic, question, title fragment, DOI, or author.

        Use this as the default discovery tool when the user asks things like:
        - "find papers about retrieval-augmented generation"
        - "do I already have this DOI in Zotero?"
        - "show sources by Kahneman in my ML collection"
        - "find papers on deception in the 'Deception Research' group"
        - "find the paper with BibTeX key smith2023" → use citation_key="smith2023"

        To retrieve all results when the total exceeds the limit, page through with offset:
        call with offset=0, then offset=100, then offset=200, etc., until you have collected
        all items (check total_results to know when to stop).

        Args:
            query: Search text to run against the Zotero library. Use "*" to list all
                   items without a text filter (useful when filtering by tag or collection only).
                   Ignored (and overridden) when citation_key is provided.
            library: Which library to search. Accepts "personal" (default), a group name
                     such as "Deception Research", or a numeric group ID. Leave empty to
                     use the default configured library.
            limit: Maximum number of matches to return per page. Max: 100. Default: 8.
            offset: Number of results to skip before returning matches. Use with limit to
                    paginate through large result sets. Default: 0.
            collection: Optional Zotero collection name or key to search inside.
            item_type: Optional Zotero item type such as 'book' or 'journalArticle'.
            tag: Optional Zotero tag filter. Matches items with this exact tag.
            citation_key: Optional Better BibTeX citation key to look up (e.g. "smith2023").
                          Searches the extra field where BBT stores "Citation Key: <key>".
                          Cannot be combined with a non-wildcard query. Requires Better BibTeX.
            include_trashed: Include trashed items when true.

        Returns:
            A compact result with source summaries. Each summary contains:
            item_key, item_type, title, creators, year, publication_title, doi, url, tags.
            `creators` is a list of `{"role": str, "name": str}` where role is the Zotero
            creatorType (author, editor, translator, …) or "" when missing.
            Also includes total_results (total matches in library) for pagination.
            When citation_key is used, also includes citation_key_matches (post-filter count).
        """
        if not query.strip():
            raise ValueError("query must not be empty")

        normalized_key = _normalize_citation_key(citation_key)
        if normalized_key and query.strip() not in ("", "*"):
            raise ValueError(
                "citation_key cannot be combined with a text query. "
                "Leave query empty or use query=\"*\" when searching by citation key."
            )

        client = scoped_client_for(get_client(), library)
        collection_key = ""
        collection_summary = None
        if collection.strip():
            try:
                resolved_collection = find_collection_by_name_or_key(client, collection)
            except ZoteroApiError as exc:
                if "No collection matched" in str(exc):
                    base_client = get_client()
                    groups = list_groups(base_client)
                    lowered = collection.strip().lower()
                    matched = [g for g in groups if lowered == g["name"].lower() or lowered in g["name"].lower()]
                    if matched:
                        names = ", ".join(f"'{g['name']}'" for g in matched[:3])
                        raise ZoteroApiError(
                            f"No collection named {collection!r} was found in the current library. "
                            f"{names} appears to be a group library — use the 'library' parameter "
                            f"(e.g. library={collection!r}) to search within it."
                        ) from exc
                raise
            collection_key = resolved_collection.get("key") or resolved_collection.get("data", {}).get("key", "")
            collection_summary = summarize_collection(resolved_collection)

        q = query.strip()
        use_list = q == "*" or not q
        if normalized_key:
            result = search_items(
                client,
                query=normalized_key,
                qmode="everything",
                collection_key=collection_key or None,
                limit=limit,
                start=offset,
                item_type=item_type.strip() or None,
                tag=tag.strip() or None,
                include_trashed=include_trashed,
            )
            needle = f"Citation Key: {normalized_key}"
            filtered = [i for i in result["items"] if needle in i.get("data", {}).get("extra", "")]
            response: dict[str, Any] = {
                "query": normalized_key,
                "library": _library_label(library),
                "collection": collection_summary,
                "offset": offset,
                "count": len(filtered),
                "total_results": result.get("total_results", result["count"]),
                "citation_key": normalized_key,
                "citation_key_matches": len(filtered),
                "sources": [summarize_item(item) for item in filtered],
            }
            return response
        elif use_list:
            result = list_items(
                client,
                collection_key=collection_key or None,
                limit=limit,
                start=offset,
                item_type=item_type.strip() or None,
                tag=tag.strip() or None,
                include_trashed=include_trashed,
            )
        else:
            result = search_items(
                client,
                query=q,
                collection_key=collection_key or None,
                limit=limit,
                start=offset,
                item_type=item_type.strip() or None,
                tag=tag.strip() or None,
                include_trashed=include_trashed,
            )
        return {
            "query": query.strip(),
            "library": _library_label(library),
            "collection": collection_summary,
            "offset": offset,
            "count": result["count"],
            "total_results": result.get("total_results", result["count"]),
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
                     Each source's `creators` is a list of `{"role": str, "name": str}`
                     (role is the Zotero creatorType: author, editor, translator, …; "" when missing).
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
            A normalized source summary. `creators` is a list of `{"role": str, "name": str}`
            where role is the Zotero creatorType (author, editor, translator, …) or "" when missing.
            If include_raw=true, adds raw_item with the original API payload.
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
            Each source's `creators` is a list of `{"role": str, "name": str}` (role is the
            Zotero creatorType: author, editor, translator, …; "" when missing).
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
            The summary's `creators` is a list of `{"role": str, "name": str}` (role is the
            Zotero creatorType: author, editor, translator, …; "" when missing).
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
        tags_to_add: str = "",
        tags_to_remove: str = "",
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

        Tag editing modes (mutually exclusive):
        - `tags`: replace the entire tag list with this CSV. Empty string leaves tags unchanged.
        - `tags_to_add` / `tags_to_remove`: apply a delta. The server fetches the item once,
          applies the delta (case-sensitive, idempotent on both sides), and writes back.
          Use this to append or strip a tag without a separate read call.
          If a name appears in both, add wins.

        Passing `tags` together with `tags_to_add` or `tags_to_remove` is an error.

        Args:
            library: Which library the item belongs to. Accepts "personal" (default),
                     a group name, or a numeric group ID.

        Returns:
            A confirmation plus an updated compact summary of the source.
            The summary's `creators` is a list of `{"role": str, "name": str}` (role is the
            Zotero creatorType: author, editor, translator, …; "" when missing).
        """
        if not item_key.strip():
            raise ValueError("item_key must not be empty")

        add_list = split_csv(tags_to_add)
        remove_list = split_csv(tags_to_remove)
        has_delta = bool(add_list or remove_list)
        has_replace = bool(tags.strip())

        if has_delta and has_replace:
            raise ValueError(
                "Use either `tags` (replace) or `tags_to_add`/`tags_to_remove` (delta), "
                "not both."
            )

        client = scoped_client_for(get_client(), library)
        extra_fields = _parse_json_object(
            extra_fields_json,
            argument_name="extra_fields_json",
        )
        collection_keys = resolve_collection_inputs(client, collections)

        fetched_item = None
        if has_delta:
            fetched_item = get_item(client, item_key.strip())

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

        if has_delta:
            current_tags = (fetched_item.get("data") or {}).get("tags", [])
            merged = compute_tag_delta(
                current_tags, to_add=add_list, to_remove=remove_list
            )
            if not tag_lists_equal(current_tags, merged):
                changes["tags"] = merged

        if not changes:
            raise ValueError(
                "Provide at least one field to change, such as title, year, doi, tags, "
                "collections, or extra_fields_json."
            )

        effective_version = current_version or (
            extract_version(fetched_item) if fetched_item is not None else None
        )

        write_result = update_item(
            client,
            item_key=item_key.strip(),
            item_data=changes,
            current_version=effective_version,
        )
        updated_item = get_item(client, item_key.strip())
        return {
            "message": "Source updated in Zotero.",
            "library": _library_label(library),
            "write_result": write_result,
            "source": summarize_item(updated_item),
        }

    @mcp.tool(
        name="find_by_tag",
        annotations=_tool_annotations(read_only=True),
    )
    def find_by_tag(
        tag: str,
        library: str = "",
        limit: int = 8,
        offset: int = 0,
        item_type: str = "",
        tags_include: str = "",
        tags_exclude: str = "",
        include_trashed: bool = False,
    ) -> dict[str, Any]:
        """Browse all top-level sources that carry a specific Zotero tag.

        Use this when the user wants every item with a given tag and has no search query, e.g.:
        - "show all papers tagged 'to-read'"
        - "list everything I tagged as 'important' in the Deception Research library"
        - "what papers do I have tagged 'ml-foundation'?"

        For Zotero saved-search style multi-tag queries (match all of A and B, exclude C and D),
        use `tags_include` and `tags_exclude` alongside the primary `tag`:
        - tag="stage/1-criterion-a", tags_exclude="excl/a-duplicate, excl/a-out-of-scope"
        - tag="ml-foundation", tags_include="reviewed", tags_exclude="archive"

        Tag matching is exact and case-sensitive. Use tags exactly as they appear in Zotero.
        Only top-level items (papers, books, etc.) are returned — PDF attachments and notes
        that carry the tag are excluded.

        To page through large tag sets use offset: call with offset=0, offset=100, etc.,
        checking total_results to know when to stop.

        Args:
            tag: Exact Zotero tag to match (required, the primary tag). Case-sensitive.
            library: Which library to browse. Accepts "personal" (default), a group name,
                     or a numeric group ID.
            limit: Maximum items to return per page. Max: 100. Default: 8.
            offset: Number of items to skip for pagination. Default: 0.
            item_type: Optional Zotero item type filter, e.g. 'journalArticle'.
            tags_include: Optional CSV of additional tags to AND with `tag`. Items must
                          carry all of them (plus `tag`) to match.
            tags_exclude: Optional CSV of tags to exclude. Items carrying any of these
                          are filtered out.
            include_trashed: Include trashed items when true.

        Returns:
            tag: The primary queried tag.
            tags_include / tags_exclude: Echoes of the filter inputs (omitted when empty).
            library: Display name of the queried library.
            offset: The current page offset.
            count: Number of items returned in this page.
            total_results: Total items matching the full tag filter in the library.
            sources: Compact source summaries (item_key, title, creators, year, doi, tags, …).
                     Each `creators` entry is `{"role": str, "name": str}` (role is the Zotero
                     creatorType: author, editor, translator, …; "" when missing).
        """
        primary = tag.strip()
        if not primary:
            raise ValueError("tag must not be empty")

        include_list = split_csv(tags_include)
        exclude_list = split_csv(tags_exclude)

        tag_filter: list[str] = [primary]
        tag_filter.extend(t for t in include_list if t != primary)
        tag_filter.extend(f"-{t}" for t in exclude_list)

        client = scoped_client_for(get_client(), library)
        result = list_items(
            client,
            tag=tag_filter,
            top_level_only=True,
            limit=limit,
            start=offset,
            item_type=item_type.strip() or None,
            include_trashed=include_trashed,
        )
        response: dict[str, Any] = {
            "tag": primary,
            "library": _library_label(library),
            "offset": offset,
            "count": result["count"],
            "total_results": result.get("total_results", result["count"]),
            "sources": [summarize_item(item) for item in result["items"]],
        }
        if include_list:
            response["tags_include"] = include_list
        if exclude_list:
            response["tags_exclude"] = exclude_list
        return response

    @mcp.tool(
        name="get_item_pdf_path",
        annotations=_tool_annotations(read_only=True),
    )
    def get_item_pdf_path(
        item_key: str,
        library: str = "",
    ) -> dict[str, Any]:
        """Return the local filesystem path(s) of PDF attachments for a Zotero item.

        Looks up the child attachments of a parent item and resolves each PDF to its
        path on disk. Works for both imported files (stored inside the Zotero data
        directory) and linked files (stored wherever you placed them).

        Requires the Zotero desktop app to be storing files locally. Configure
        ZOTERO_DATA_DIR if your Zotero data directory is not the default ~/Zotero.

        Use this when the user asks:
        - "where is the PDF for item ABCD1234?"
        - "give me the local path of this paper's PDF"
        - "open the PDF for this item in my editor"

        Args:
            item_key: Zotero item key of the parent item.
            library: Which library the item belongs to. Accepts "personal" (default),
                     a group name, or a numeric group ID.

        Returns:
            item_key: The queried item key.
            pdfs: List of resolved PDF attachments, each with attachment_key, filename,
                  link_mode, and local_path (null if the path could not be determined).
        """
        import os

        if not item_key.strip():
            raise ValueError("item_key must not be empty")

        client = scoped_client_for(get_client(), library)
        data_dir = client.config.zotero_data_dir

        children = list_item_children(client, item_key.strip(), item_type="attachment")
        pdfs = []
        for child in children:
            data = child.get("data", {})
            content_type = data.get("contentType", "")
            if content_type != "application/pdf":
                continue

            key = child.get("key") or data.get("key", "")
            filename = data.get("filename", "")
            link_mode = data.get("linkMode", "")

            if link_mode in ("imported_file", "imported_url"):
                local_path = os.path.join(data_dir, "storage", key, filename) if key and filename else None
            elif link_mode == "linked_file":
                raw_path = data.get("path", "")
                # Zotero stores relative linked paths with an "attachments:" prefix
                if raw_path.startswith("attachments:"):
                    base = os.path.join(data_dir, "attachments")
                    local_path = os.path.join(base, raw_path[len("attachments:"):])
                else:
                    local_path = raw_path or None
            else:
                local_path = None

            pdfs.append({
                "attachment_key": key,
                "filename": filename,
                "link_mode": link_mode,
                "local_path": local_path,
            })

        return {
            "item_key": item_key.strip(),
            "library": _library_label(library),
            "pdfs": pdfs,
        }
