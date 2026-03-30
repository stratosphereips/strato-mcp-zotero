"""Tests for Zotero item API wrappers."""
from __future__ import annotations

import json

import httpx

from zotero_mcp.config import Config
from zotero_mcp.zotero.client import ZoteroClient
from zotero_mcp.zotero.items import create_item, delete_item, list_items, update_item


def test_list_items_uses_expected_path_and_params(valid_config):
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["params"] = dict(request.url.params)
        return httpx.Response(
            200,
            json=[{"key": "ABCD1234"}],
            headers={"Total-Results": "1"},
            request=request,
        )

    transport = httpx.MockTransport(handler)
    client = ZoteroClient(valid_config, httpx.Client(transport=transport, base_url=valid_config.api_base_url))

    result = list_items(
        client,
        collection_key="COLL1234",
        top_level_only=True,
        limit=200,
        item_type="book",
        tag="ml",
        include_trashed=True,
    )

    assert captured["path"] == "/users/12345/collections/COLL1234/items/top"
    assert captured["params"] == {
        "format": "json",
        "limit": "100",
        "start": "0",
        "sort": "dateModified",
        "direction": "desc",
        "itemType": "book",
        "tag": "ml",
        "includeTrashed": "1",
    }
    assert result["count"] == 1
    assert result["total_results"] == 1


def test_create_item_posts_single_item_array_and_write_token(valid_config):
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content.decode("utf-8"))
        captured["write_token"] = request.headers.get("Zotero-Write-Token")
        return httpx.Response(
            200,
            json={"successful": {"0": "ABCD1234"}},
            headers={"Last-Modified-Version": "88"},
            request=request,
        )

    transport = httpx.MockTransport(handler)
    client = ZoteroClient(valid_config, httpx.Client(transport=transport, base_url=valid_config.api_base_url))

    result = create_item(client, {"itemType": "book", "title": "Test"}, write_token="token123")

    assert captured["path"] == "/users/12345/items"
    assert captured["body"] == [{"itemType": "book", "title": "Test"}]
    assert captured["write_token"] == "token123"
    assert result["last_modified_version"] == "88"


def test_update_item_fetches_version_when_missing(valid_config):
    requests: list[tuple[str, str, object | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8")) if request.content else None
        requests.append((request.method, request.url.path, body))
        if request.method == "GET":
            return httpx.Response(
                200,
                json={"key": "ABCD1234", "version": 44, "data": {"title": "Old"}},
                request=request,
            )
        return httpx.Response(
            200,
            json={"successful": {"0": "ABCD1234"}},
            request=request,
        )

    transport = httpx.MockTransport(handler)
    client = ZoteroClient(valid_config, httpx.Client(transport=transport, base_url=valid_config.api_base_url))

    update_item(client, "ABCD1234", {"title": "New"})

    assert requests == [
        ("GET", "/users/12345/items/ABCD1234", None),
        ("POST", "/users/12345/items", [{"title": "New", "key": "ABCD1234", "version": 44}]),
    ]


def test_delete_item_fetches_version_when_missing(valid_config):
    captured: list[tuple[str, str, str | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(
            (
                request.method,
                request.url.path,
                request.headers.get("If-Unmodified-Since-Version"),
            )
        )
        if request.method == "GET":
            return httpx.Response(
                200,
                json={"key": "ABCD1234", "version": 44},
                request=request,
            )
        return httpx.Response(204, request=request)

    transport = httpx.MockTransport(handler)
    client = ZoteroClient(valid_config, httpx.Client(transport=transport, base_url=valid_config.api_base_url))

    result = delete_item(client, "ABCD1234")

    assert captured == [
        ("GET", "/users/12345/items/ABCD1234", None),
        ("DELETE", "/users/12345/items/ABCD1234", "44"),
    ]
    assert result["deleted"] is True


def test_user_id_can_be_resolved_from_key_metadata():
    config = Config(
        api_key="test-api-key",
        library_type="user",
        library_id=None,
        api_base_url="https://api.zotero.org",
        api_version="3",
        default_limit=25,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/keys/test-api-key"
        return httpx.Response(200, json={"userID": 67890}, request=request)

    transport = httpx.MockTransport(handler)
    client = ZoteroClient(config, httpx.Client(transport=transport, base_url=config.api_base_url))

    assert client.get_library_prefix() == "/users/67890"
