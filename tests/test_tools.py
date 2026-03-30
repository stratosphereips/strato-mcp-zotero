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
    def __init__(self):
        self.prefix = "/users/12345"
        self.calls: list[tuple[str, str]] = []

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
                    "creators": [{"firstName": "Ada", "lastName": "Lovelace"}],
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
                        "creators": [{"firstName": "Grace", "lastName": "Hopper"}],
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

def test_find_collection_by_name_recurses():
    from zotero_mcp.zotero.library import find_collection_by_name_or_key

    client = StubClient()
    result = find_collection_by_name_or_key(client, "Week 1")
    assert result["key"] == "SUB12345"


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
