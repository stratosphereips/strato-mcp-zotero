"""Shared pytest fixtures."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from zotero_mcp.config import Config


@pytest.fixture(autouse=True)
def _no_load_dotenv(monkeypatch):
    monkeypatch.setattr("zotero_mcp.config.load_dotenv", lambda **_: None)


@pytest.fixture()
def valid_config() -> Config:
    return Config(
        api_key="test-api-key",
        library_type="user",
        library_id="12345",
        api_base_url="https://api.zotero.org",
        api_version="3",
        default_limit=25,
    )


@pytest.fixture()
def mock_client() -> MagicMock:
    client = MagicMock()
    client.get_library_prefix.return_value = "/users/12345"
    return client


def make_response(
    status_code: int,
    data: Any | None = None,
    *,
    headers: dict[str, str] | None = None,
    url: str = "https://api.zotero.org/users/12345/items",
    method: str = "GET",
) -> httpx.Response:
    request = httpx.Request(method, url)
    content = b""
    if data is not None:
        content = json.dumps(data).encode("utf-8")
    response_headers = dict(headers or {})
    if data is not None:
        response_headers.setdefault("Content-Type", "application/json")
    return httpx.Response(
        status_code=status_code,
        headers=response_headers,
        content=content,
        request=request,
    )
