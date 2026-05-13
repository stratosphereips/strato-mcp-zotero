"""Workflow-first MCP tool integration tests."""
from __future__ import annotations

import pytest

from zotero_mcp.zotero.client import ZoteroApiError


class ToolRecorder:
    """Captures tool functions registered via @recorder.tool()."""

    def __init__(self):
        self._tools: dict[str, callable] = {}

    def tool(self, name=None, **_kwargs):
        def decorator(fn):
            self._tools[name or fn.__name__] = fn
            return fn

        return decorator

    def call(self, name: str, **kwargs):
        return self._tools[name](**kwargs)


class StubClient:
    config = None

    def __init__(self):
        self.prefix = "/users/12345"
        self.calls: list[tuple[str, str]] = []

    def get_user_id(self) -> str:
        return "12345"

    def get_library_prefix(self) -> str:
        return self.prefix

    def request_json(self, method, path, **kwargs):
        self.calls.append((method, path))
        if path.endswith("/items/new"):
            return {"itemType": "book", "title": "", "creators": []}, None
        if "/collections/" in path and method == "GET" and not path.endswith("/collections") and not path.endswith("/items") and not path.endswith("/collections"):
            if path.endswith("/collections/COLL1234"):
                return {"key": "COLL1234", "data": {"name": "Reading Queue"}}, None
            raise ZoteroApiError("missing", status_code=404)
        if path.endswith("/collections/COLL1234") and method == "GET":
            return {"key": "COLL1234", "data": {"name": "Reading Queue"}}, None
        if path.endswith("/collections/COLL1234/collections") and method == "GET":
            return [{"key": "SUB12345", "data": {"name": "Week 1"}}], _response_headers()
        if path.endswith("/collections") and method == "GET":
            if path.count("/collections") > 1:
                return [], _response_headers()
            return [
                {"key": "COLL1234", "data": {"name": "Reading Queue"}},
                {"key": "COLL5678", "data": {"name": "Machine Learning"}},
            ], _response_headers()
        if path.endswith("/collections/COLL1234/collections") and method == "GET":
            return [{"key": "SUB12345", "data": {"name": "Week 1"}}], _response_headers()
        if path.endswith("/collections/COLL1234/items") and method == "GET":
            return [
                {
                    "key": "ABCD1234",
                    "data": {"itemType": "book", "title": "Test Book", "creators": []},
                }
            ], _response_headers()
        if path.endswith("/items/ABCD1234") and method == "GET":
            return {
                "key": "ABCD1234",
                "version": 10,
                "data": {
                    "itemType": "book",
                    "title": "Test Book",
                    "creators": [
                        {"creatorType": "author", "firstName": "Ada", "lastName": "Lovelace"}
                    ],
                    "date": "1843",
                    "DOI": "10.1000/test",
                    "tags": [{"tag": "history"}],
                },
            }, None
        if path.endswith("/items") and method == "POST":
            return {"successful": {"0": "ABCD1234"}}, _response_headers()
        if path.endswith("/items") and method == "GET":
            return [
                {
                    "key": "ABCD1234",
                    "data": {
                        "itemType": "journalArticle",
                        "title": "Transformer Scaling Laws",
                        "creators": [
                            {"creatorType": "author", "firstName": "Grace", "lastName": "Hopper"}
                        ],
                        "date": "2024",
                        "DOI": "10.1000/example",
                    },
                }
            ], _response_headers()
        if path.endswith("/items/ABCD1234") and method == "DELETE":
            return None, _response_headers()
        raise AssertionError(f"Unhandled request: {method} {path}")


class _response_headers:
    headers = {"Total-Results": "1", "Last-Modified-Version": "11"}


class TestLibraryTools:
    @pytest.fixture(autouse=True)
    def setup(self):
        from zotero_mcp.tools.library import register_library_tools

        self.client = StubClient()
        self.recorder = ToolRecorder()
        register_library_tools(self.recorder, lambda: self.client)

    def test_find_library_sources_returns_compact_results(self):
        result = self.recorder.call("find_library_sources", query="transformers")
        assert result["count"] == 1
        assert result["sources"][0]["title"] == "Transformer Scaling Laws"

    def test_find_library_sources_rejects_empty_query(self):
        with pytest.raises(ValueError):
            self.recorder.call("find_library_sources", query="   ")

    def test_find_library_sources_returns_total_results(self):
        result = self.recorder.call("find_library_sources", query="transformers")
        assert "total_results" in result
        assert result["total_results"] == 1

    def test_find_library_sources_default_offset_is_zero(self):
        result = self.recorder.call("find_library_sources", query="transformers")
        assert result["offset"] == 0

    def test_find_library_sources_passes_offset_to_api(self):
        result = self.recorder.call("find_library_sources", query="transformers", offset=100)
        assert result["offset"] == 100

    def test_find_library_sources_wildcard_passes_offset(self):
        result = self.recorder.call("find_library_sources", query="*", offset=50)
        assert result["offset"] == 50

    def test_inspect_saved_source_requires_key(self):
        with pytest.raises(ValueError):
            self.recorder.call("inspect_saved_source", item_key="")

    def test_review_collection_resolves_collection_and_returns_sources(self):
        result = self.recorder.call("review_collection", collection="Reading Queue")
        assert result["collection"]["collection_key"] == "COLL1234"
        assert result["sources"][0]["title"] == "Test Book"

    def test_save_source_to_library_returns_saved_summary(self):
        result = self.recorder.call(
            "save_source_to_library",
            item_type="book",
            title="Analytical Engine Notes",
            creators="Ada Lovelace",
            collections="Reading Queue",
        )
        assert result["source"]["item_key"] == "ABCD1234"

    def test_update_saved_source_requires_changes(self):
        with pytest.raises(ValueError):
            self.recorder.call("update_saved_source", item_key="ABCD1234")

    def test_update_saved_source_returns_updated_summary(self):
        result = self.recorder.call(
            "update_saved_source",
            item_key="ABCD1234",
            doi="10.1000/updated",
        )
        assert result["source"]["item_key"] == "ABCD1234"

class CitationKeyStubClient(StubClient):
    """Returns items with/without citation keys in extra for testing citation_key search."""

    def request_json(self, method, path, **kwargs):
        if path.endswith("/items") and method == "GET":
            params = kwargs.get("params", {})
            if params.get("qmode") == "everything":
                return [
                    {
                        "key": "CITE0001",
                        "data": {
                            "itemType": "journalArticle",
                            "title": "Exact Match Paper",
                            "creators": [],
                            "date": "2023",
                            "extra": "Citation Key: smith2023\nsome other info",
                        },
                    },
                    {
                        "key": "CITE0002",
                        "data": {
                            "itemType": "journalArticle",
                            "title": "False Positive Paper",
                            "creators": [],
                            "date": "2023",
                            "abstractNote": "This cites smith2023 in the abstract.",
                            "extra": "",
                        },
                    },
                ], _response_headers_n(2)
        return super().request_json(method, path, **kwargs)


class _response_headers_n:
    def __init__(self, n: int):
        self.headers = {"Total-Results": str(n), "Last-Modified-Version": "11"}


class TagStubClient(StubClient):
    """Returns tagged items for find_by_tag tests; captures the last params dict."""

    def __init__(self):
        super().__init__()
        self.last_params: dict | None = None

    def request_json(self, method, path, **kwargs):
        if path.endswith("/items/top") and method == "GET":
            self.last_params = kwargs.get("params")
            return [
                {
                    "key": "TAG00001",
                    "data": {
                        "itemType": "journalArticle",
                        "title": "Important Paper",
                        "creators": [],
                        "date": "2022",
                        "tags": [{"tag": "to-read"}],
                    },
                }
            ], _response_headers()
        return super().request_json(method, path, **kwargs)


class TestCitationKeySearch:
    @pytest.fixture(autouse=True)
    def setup(self):
        from zotero_mcp.tools.library import register_library_tools

        self.client = CitationKeyStubClient()
        self.recorder = ToolRecorder()
        register_library_tools(self.recorder, lambda: self.client)

    def test_citation_key_finds_exact_match(self):
        result = self.recorder.call("find_library_sources", query="*", citation_key="smith2023")
        assert result["citation_key_matches"] == 1
        assert result["sources"][0]["item_key"] == "CITE0001"

    def test_citation_key_filters_out_false_positives(self):
        result = self.recorder.call("find_library_sources", query="*", citation_key="smith2023")
        assert result["count"] == 1
        keys = [s["item_key"] for s in result["sources"]]
        assert "CITE0002" not in keys

    def test_citation_key_no_match_returns_empty(self):
        result = self.recorder.call("find_library_sources", query="*", citation_key="nobody2099")
        assert result["citation_key_matches"] == 0
        assert result["sources"] == []

    def test_citation_key_strips_bbt_prefix(self):
        result = self.recorder.call(
            "find_library_sources", query="*", citation_key="Citation Key: smith2023"
        )
        assert result["citation_key"] == "smith2023"
        assert result["citation_key_matches"] == 1

    def test_citation_key_is_case_sensitive(self):
        result = self.recorder.call("find_library_sources", query="*", citation_key="Smith2023")
        assert result["citation_key_matches"] == 0

    def test_citation_key_with_text_query_raises(self):
        with pytest.raises(ValueError):
            self.recorder.call(
                "find_library_sources", query="transformers", citation_key="smith2023"
            )

    def test_empty_citation_key_is_ignored(self):
        result = self.recorder.call("find_library_sources", query="transformers", citation_key="")
        assert "citation_key" not in result
        assert "citation_key_matches" not in result

    def test_citation_key_present_in_response(self):
        result = self.recorder.call("find_library_sources", query="*", citation_key="smith2023")
        assert result["citation_key"] == "smith2023"


class TestFindByTag:
    @pytest.fixture(autouse=True)
    def setup(self):
        from zotero_mcp.tools.library import register_library_tools

        self.client = TagStubClient()
        self.recorder = ToolRecorder()
        register_library_tools(self.recorder, lambda: self.client)

    def test_find_by_tag_returns_matching_items(self):
        result = self.recorder.call("find_by_tag", tag="to-read")
        assert result["tag"] == "to-read"
        assert result["count"] == 1
        assert result["sources"][0]["title"] == "Important Paper"

    def test_find_by_tag_empty_tag_raises(self):
        with pytest.raises(ValueError):
            self.recorder.call("find_by_tag", tag="   ")

    def test_find_by_tag_default_offset_is_zero(self):
        result = self.recorder.call("find_by_tag", tag="to-read")
        assert result["offset"] == 0

    def test_find_by_tag_passes_offset(self):
        result = self.recorder.call("find_by_tag", tag="to-read", offset=10)
        assert result["offset"] == 10

    def test_find_by_tag_has_total_results(self):
        result = self.recorder.call("find_by_tag", tag="to-read")
        assert "total_results" in result

    def test_find_by_tag_sends_single_tag_as_list(self):
        self.recorder.call("find_by_tag", tag="to-read")
        assert self.client.last_params["tag"] == ["to-read"]

    def test_find_by_tag_includes_extra_tags_anded(self):
        self.recorder.call(
            "find_by_tag", tag="stage/1", tags_include="reviewed, ready"
        )
        assert self.client.last_params["tag"] == ["stage/1", "reviewed", "ready"]

    def test_find_by_tag_excludes_prefix_dash(self):
        self.recorder.call(
            "find_by_tag",
            tag="stage/1-criterion-a",
            tags_exclude="excl/a-duplicate, excl/a-out-of-scope",
        )
        assert self.client.last_params["tag"] == [
            "stage/1-criterion-a",
            "-excl/a-duplicate",
            "-excl/a-out-of-scope",
        ]

    def test_find_by_tag_include_and_exclude_combined(self):
        self.recorder.call(
            "find_by_tag",
            tag="A",
            tags_include="B",
            tags_exclude="C",
        )
        assert self.client.last_params["tag"] == ["A", "B", "-C"]

    def test_find_by_tag_dedupes_primary_from_include(self):
        self.recorder.call("find_by_tag", tag="A", tags_include="A, B")
        assert self.client.last_params["tag"] == ["A", "B"]

    def test_find_by_tag_echoes_filters_in_response(self):
        result = self.recorder.call(
            "find_by_tag", tag="A", tags_include="B", tags_exclude="C"
        )
        assert result["tags_include"] == ["B"]
        assert result["tags_exclude"] == ["C"]

    def test_find_by_tag_omits_filter_echo_when_empty(self):
        result = self.recorder.call("find_by_tag", tag="A")
        assert "tags_include" not in result
        assert "tags_exclude" not in result

    def test_find_by_tag_tool_is_registered(self):
        from zotero_mcp.tools.library import register_library_tools

        recorder = ToolRecorder()
        register_library_tools(recorder, lambda: self.client)
        assert "find_by_tag" in recorder._tools


class TagDeltaStubClient(StubClient):
    """Serves an item with configurable tags + version, captures POST bodies."""

    def __init__(self, current_tags=None, version=10):
        super().__init__()
        self.current_tags = current_tags if current_tags is not None else [{"tag": "history"}]
        self.version = version
        self.last_post_body = None

    def request_json(self, method, path, **kwargs):
        if path.endswith("/items/ABCD1234") and method == "GET":
            return {
                "key": "ABCD1234",
                "version": self.version,
                "data": {
                    "itemType": "book",
                    "title": "Test Book",
                    "creators": [],
                    "tags": list(self.current_tags),
                },
            }, None
        if path.endswith("/items") and method == "POST":
            self.last_post_body = kwargs.get("json_body")
            return {"successful": {"0": "ABCD1234"}}, _response_headers()
        return super().request_json(method, path, **kwargs)


class TestUpdateSavedSourceTagDelta:
    def _setup(self, current_tags=None, version=10):
        from zotero_mcp.tools.library import register_library_tools

        client = TagDeltaStubClient(current_tags=current_tags, version=version)
        recorder = ToolRecorder()
        register_library_tools(recorder, lambda: client)
        return client, recorder

    def test_update_saved_source_tags_add_appends_to_existing(self):
        client, recorder = self._setup(current_tags=[{"tag": "a"}], version=42)
        recorder.call("update_saved_source", item_key="ABCD1234", tags_to_add="b")
        assert client.last_post_body[0]["tags"] == [{"tag": "a"}, {"tag": "b"}]
        assert client.last_post_body[0]["version"] == 42

    def test_update_saved_source_tags_remove_drops_existing(self):
        client, recorder = self._setup(current_tags=[{"tag": "a"}, {"tag": "b"}])
        recorder.call("update_saved_source", item_key="ABCD1234", tags_to_remove="a")
        assert client.last_post_body[0]["tags"] == [{"tag": "b"}]

    def test_update_saved_source_tags_add_and_remove_combined(self):
        client, recorder = self._setup(current_tags=[{"tag": "a"}, {"tag": "b"}])
        recorder.call(
            "update_saved_source",
            item_key="ABCD1234",
            tags_to_add="c",
            tags_to_remove="a",
        )
        assert client.last_post_body[0]["tags"] == [{"tag": "b"}, {"tag": "c"}]

    def test_update_saved_source_rejects_replace_with_delta(self):
        _, recorder = self._setup()
        with pytest.raises(ValueError):
            recorder.call(
                "update_saved_source",
                item_key="ABCD1234",
                tags="x",
                tags_to_add="y",
            )

    def test_update_saved_source_tags_add_idempotent_no_change(self):
        client, recorder = self._setup(current_tags=[{"tag": "a"}])
        with pytest.raises(ValueError):
            recorder.call("update_saved_source", item_key="ABCD1234", tags_to_add="a")
        assert client.last_post_body is None

    def test_update_saved_source_tags_remove_idempotent_no_change(self):
        client, recorder = self._setup(current_tags=[{"tag": "a"}])
        with pytest.raises(ValueError):
            recorder.call("update_saved_source", item_key="ABCD1234", tags_to_remove="z")
        assert client.last_post_body is None

    def test_update_saved_source_tags_delta_preserves_automatic_type(self):
        client, recorder = self._setup(
            current_tags=[{"tag": "auto", "type": 1}, {"tag": "manual"}],
        )
        recorder.call("update_saved_source", item_key="ABCD1234", tags_to_add="extra")
        assert client.last_post_body[0]["tags"] == [
            {"tag": "auto", "type": 1},
            {"tag": "manual"},
            {"tag": "extra"},
        ]


def test_find_collection_by_name_recurses():
    from zotero_mcp.zotero.library import find_collection_by_name_or_key

    client = StubClient()
    result = find_collection_by_name_or_key(client, "Week 1")
    assert result["key"] == "SUB12345"


def test_summarize_item_returns_creator_role_and_name():
    from zotero_mcp.zotero.library import summarize_item

    item = {
        "key": "X",
        "data": {
            "itemType": "book",
            "title": "T",
            "creators": [
                {"creatorType": "editor", "firstName": "Quanyan", "lastName": "Zhu"}
            ],
        },
    }
    assert summarize_item(item)["creators"] == [
        {"role": "editor", "name": "Quanyan Zhu"}
    ]


def test_summarize_item_creator_missing_type_returns_empty_role():
    from zotero_mcp.zotero.library import summarize_item

    item = {
        "key": "X",
        "data": {
            "itemType": "book",
            "title": "T",
            "creators": [{"firstName": "Ada", "lastName": "Lovelace"}],
        },
    }
    assert summarize_item(item)["creators"] == [
        {"role": "", "name": "Ada Lovelace"}
    ]


def test_summarize_item_creator_with_single_name_field():
    from zotero_mcp.zotero.library import summarize_item

    item = {
        "key": "X",
        "data": {
            "itemType": "report",
            "title": "T",
            "creators": [{"creatorType": "author", "name": "World Health Organization"}],
        },
    }
    assert summarize_item(item)["creators"] == [
        {"role": "author", "name": "World Health Organization"}
    ]


def test_summarize_item_distinguishes_authors_and_editors():
    from zotero_mcp.zotero.library import summarize_item

    item = {
        "key": "X",
        "data": {
            "itemType": "bookSection",
            "title": "T",
            "creators": [
                {"creatorType": "author", "firstName": "Neil", "lastName": "Rowe"},
                {"creatorType": "editor", "firstName": "Quanyan", "lastName": "Zhu"},
            ],
        },
    }
    creators = summarize_item(item)["creators"]
    authors = [c["name"] for c in creators if c["role"] == "author"]
    editors = [c["name"] for c in creators if c["role"] == "editor"]
    assert authors == ["Neil Rowe"]
    assert editors == ["Quanyan Zhu"]


def test_inspect_saved_source_returns_structured_creators():
    from zotero_mcp.tools.library import register_library_tools

    class MixedCreatorClient(StubClient):
        def request_json(self, method, path, **kwargs):
            if path.endswith("/items/ABCD1234") and method == "GET":
                return {
                    "key": "ABCD1234",
                    "version": 10,
                    "data": {
                        "itemType": "bookSection",
                        "title": "Deception in LNCS",
                        "creators": [
                            {"creatorType": "author", "firstName": "Neil", "lastName": "Rowe"},
                            {"creatorType": "editor", "firstName": "Quanyan", "lastName": "Zhu"},
                        ],
                    },
                }, None
            return super().request_json(method, path, **kwargs)

    recorder = ToolRecorder()
    register_library_tools(recorder, lambda: MixedCreatorClient())
    result = recorder.call("inspect_saved_source", item_key="ABCD1234")
    assert result["creators"] == [
        {"role": "author", "name": "Neil Rowe"},
        {"role": "editor", "name": "Quanyan Zhu"},
    ]


def test_collection_resolution_reports_ambiguous_matches():
    from zotero_mcp.tools.library import register_library_tools

    class AmbiguousCollectionClient(StubClient):
        def request_json(self, method, path, **kwargs):
            if path.endswith("/UNKNOWN") and method == "GET":
                raise ZoteroApiError("missing", status_code=404)
            if path.endswith("/collections") and method == "GET":
                return [
                    {"key": "COLL1", "data": {"name": "Reading Queue"}},
                    {"key": "COLL2", "data": {"name": "Reading Queue Archive"}},
                ], _response_headers()
            return super().request_json(method, path, **kwargs)

    recorder = ToolRecorder()
    register_library_tools(recorder, lambda: AmbiguousCollectionClient())

    with pytest.raises(ZoteroApiError):
        recorder.call("review_collection", collection="UNKNOWN")
