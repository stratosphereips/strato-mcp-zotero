"""Authenticated Zotero Web API client."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

import httpx

from zotero_mcp.config import Config

logger = logging.getLogger(__name__)


@dataclass
class ZoteroApiError(Exception):
    """Raised when the Zotero API returns an error."""

    message: str
    status_code: int | None = None
    response_body: str | None = None

    def __str__(self) -> str:
        if self.status_code is None:
            return self.message
        return f"{self.message} (HTTP {self.status_code})"


class ZoteroClient:
    """Thin HTTP client for the Zotero Web API."""

    def __init__(self, config: Config, http_client: httpx.Client | None = None) -> None:
        self.config = config
        self._base_headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {config.api_key}",
            "Zotero-API-Version": config.api_version,
        }
        self._http = http_client or httpx.Client(
            base_url=config.api_base_url,
            timeout=30.0,
        )
        self._owns_http_client = http_client is None
        self._library_prefix: str | None = None
        self._user_id: str | None = None

    def close(self) -> None:
        if self._owns_http_client:
            self._http.close()

    def get_library_prefix(self) -> str:
        """Return `/users/<id>` or `/groups/<id>` for the configured library."""
        if self._library_prefix:
            return self._library_prefix

        if self.config.library_id:
            self._library_prefix = (
                f"/{self.config.library_prefix_type}/{self.config.library_id}"
            )
            return self._library_prefix

        if self.config.library_type != "user":
            raise ZoteroApiError(
                "A library ID is required for non-user libraries."
            )

        user_id = self.get_user_id()
        self._library_prefix = f"/users/{user_id}"
        return self._library_prefix

    def get_user_id(self) -> str:
        """Return the Zotero user ID for the authenticated API key."""
        if self._user_id:
            return self._user_id

        key_info, _ = self.request_json(
            "GET",
            f"/keys/{self.config.api_key}",
            auth=False,
        )

        user_id = key_info.get("userID")
        if not user_id:
            raise ZoteroApiError(
                "Failed to resolve Zotero user ID from the API key metadata."
            )

        self._user_id = str(user_id)
        return self._user_id

    def list_groups(self) -> list[dict[str, Any]]:
        """Return all groups the authenticated user has access to."""
        user_id = self.get_user_id()
        data, _ = self.request_json("GET", f"/users/{user_id}/groups", params={"format": "json"})
        return data if isinstance(data, list) else []

    def request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any | None = None,
        headers: dict[str, str] | None = None,
        auth: bool = True,
    ) -> tuple[Any, httpx.Response]:
        """Perform an HTTP request and decode the JSON response when present."""
        request_headers = dict(self._base_headers)
        request_headers.update(headers or {})
        if not auth:
            request_headers.pop("Authorization", None)

        try:
            response = self._http.request(
                method=method,
                url=path,
                params=params,
                json=json_body,
                headers=request_headers or None,
            )
        except httpx.HTTPError as exc:
            raise ZoteroApiError(f"Network error while calling Zotero API: {exc}") from exc

        if response.is_error:
            raise ZoteroApiError(
                _format_error_message(response),
                status_code=response.status_code,
                response_body=response.text,
            )

        if response.status_code == 204 or not response.content:
            return None, response

        try:
            return response.json(), response
        except json.JSONDecodeError as exc:
            raise ZoteroApiError(
                "Failed to decode JSON response from Zotero API.",
                status_code=response.status_code,
                response_body=response.text,
            ) from exc


class ScopedClient:
    """Wraps a ZoteroClient with a fixed library prefix for multi-library operations."""

    def __init__(self, client: ZoteroClient, prefix: str) -> None:
        self._client = client
        self._prefix = prefix
        self.config = client.config

    def get_library_prefix(self) -> str:
        return self._prefix

    def request_json(self, *args: Any, **kwargs: Any) -> tuple[Any, httpx.Response]:
        return self._client.request_json(*args, **kwargs)

    def get_user_id(self) -> str:
        return self._client.get_user_id()

    def list_groups(self) -> list[dict[str, Any]]:
        return self._client.list_groups()

    def close(self) -> None:
        pass  # The underlying client is managed externally


def build_client(config: Config) -> ZoteroClient:
    """Return an authenticated Zotero Web API client."""
    logger.debug("Building Zotero client")
    return ZoteroClient(config)


def build_list_result(
    data: list[dict[str, Any]],
    response: httpx.Response,
    *,
    start: int,
    limit: int,
) -> dict[str, Any]:
    """Return list data with common pagination metadata."""
    total_results = response.headers.get("Total-Results")
    last_modified_version = response.headers.get("Last-Modified-Version")

    result: dict[str, Any] = {
        "items": data,
        "count": len(data),
        "start": start,
        "limit": limit,
    }

    if total_results is not None:
        try:
            result["total_results"] = int(total_results)
        except ValueError:
            result["total_results"] = total_results

    if last_modified_version is not None:
        result["last_modified_version"] = last_modified_version

    links = _parse_link_header(response.headers.get("Link", ""))
    if links:
        result["links"] = links

    return result


def extract_version(obj: dict[str, Any]) -> int | None:
    """Extract a version number from a Zotero API object."""
    version = obj.get("version")
    if isinstance(version, int):
        return version

    data = obj.get("data")
    if isinstance(data, dict):
        nested_version = data.get("version")
        if isinstance(nested_version, int):
            return nested_version

    return None


def _format_error_message(response: httpx.Response) -> str:
    reason = response.reason_phrase or "Unknown error"
    if response.text:
        snippet = response.text.strip().replace("\n", " ")
        if len(snippet) > 200:
            snippet = snippet[:197] + "..."
        return f"Zotero API request failed: {reason}. {snippet}"
    return f"Zotero API request failed: {reason}."


def _parse_link_header(link_header: str) -> dict[str, str]:
    links: dict[str, str] = {}
    if not link_header:
        return links

    for part in link_header.split(","):
        section = part.strip()
        if ";" not in section:
            continue
        url_part, *attributes = [segment.strip() for segment in section.split(";")]
        if not url_part.startswith("<") or not url_part.endswith(">"):
            continue

        url = url_part[1:-1]
        rel = None
        for attribute in attributes:
            if attribute.startswith("rel="):
                rel = attribute.split("=", 1)[1].strip('"')
                break
        if rel:
            links[rel] = url

    return links
