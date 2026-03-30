"""Tests for environment-driven configuration."""
from __future__ import annotations

import pytest

from zotero_mcp.config import ConfigurationError, load_config


def test_load_config_requires_api_key(monkeypatch):
    monkeypatch.delenv("ZOTERO_API_KEY", raising=False)
    with pytest.raises(ConfigurationError):
        load_config()


def test_load_config_rejects_invalid_library_type(monkeypatch):
    monkeypatch.setenv("ZOTERO_API_KEY", "key")
    monkeypatch.setenv("ZOTERO_LIBRARY_TYPE", "team")
    with pytest.raises(ConfigurationError):
        load_config()


def test_load_config_requires_group_id(monkeypatch):
    monkeypatch.setenv("ZOTERO_API_KEY", "key")
    monkeypatch.setenv("ZOTERO_LIBRARY_TYPE", "group")
    monkeypatch.delenv("ZOTERO_LIBRARY_ID", raising=False)
    with pytest.raises(ConfigurationError):
        load_config()


def test_load_config_accepts_user_without_library_id(monkeypatch):
    monkeypatch.setenv("ZOTERO_API_KEY", "key")
    monkeypatch.setenv("ZOTERO_LIBRARY_TYPE", "user")
    monkeypatch.delenv("ZOTERO_LIBRARY_ID", raising=False)
    config = load_config()
    assert config.library_type == "user"
    assert config.library_id is None
