"""Configuration loading via environment variables / .env file."""
from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass

from dotenv import load_dotenv

# All logging goes to stderr so stdout stays clean for MCP stdio transport
logging.basicConfig(
    stream=sys.stderr,
    level=os.getenv("LOG_LEVEL", "WARNING").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)

DEFAULT_API_BASE_URL = "https://api.zotero.org"
DEFAULT_API_VERSION = "3"
DEFAULT_LIBRARY_TYPE = "user"
DEFAULT_LIMIT = 25


class ConfigurationError(Exception):
    """Raised when required configuration is missing or invalid."""


@dataclass
class Config:
    api_key: str
    library_type: str = DEFAULT_LIBRARY_TYPE
    library_id: str | None = None
    api_base_url: str = DEFAULT_API_BASE_URL
    api_version: str = DEFAULT_API_VERSION
    default_limit: int = DEFAULT_LIMIT
    log_level: str = "WARNING"

    def __post_init__(self) -> None:
        self.library_type = self.library_type.strip().lower()
        if self.library_type not in {"user", "group"}:
            raise ConfigurationError(
                "ZOTERO_LIBRARY_TYPE must be either 'user' or 'group'."
            )

        if self.library_id is not None:
            stripped = self.library_id.strip()
            self.library_id = stripped or None

        if self.library_type == "group" and not self.library_id:
            raise ConfigurationError(
                "ZOTERO_LIBRARY_ID is required when ZOTERO_LIBRARY_TYPE=group."
            )

        try:
            self.default_limit = int(self.default_limit)
        except (TypeError, ValueError) as exc:
            raise ConfigurationError("ZOTERO_DEFAULT_LIMIT must be an integer.") from exc

        if self.default_limit < 1:
            raise ConfigurationError("ZOTERO_DEFAULT_LIMIT must be greater than 0.")

        self.api_base_url = self.api_base_url.rstrip("/")
        self.api_version = str(self.api_version).strip() or DEFAULT_API_VERSION

    @property
    def library_prefix_type(self) -> str:
        """Return the API path segment for the configured library type."""
        return "users" if self.library_type == "user" else "groups"


def load_config() -> Config:
    """Load configuration from environment variables and an optional .env file."""
    load_dotenv()

    api_key = os.getenv("ZOTERO_API_KEY", "").strip()
    if not api_key:
        raise ConfigurationError(
            "Missing required environment variable: ZOTERO_API_KEY. "
            "Copy .env.example to .env and fill in your Zotero API key."
        )

    return Config(
        api_key=api_key,
        library_type=os.getenv("ZOTERO_LIBRARY_TYPE", DEFAULT_LIBRARY_TYPE),
        library_id=os.getenv("ZOTERO_LIBRARY_ID"),
        api_base_url=os.getenv("ZOTERO_API_BASE_URL", DEFAULT_API_BASE_URL),
        api_version=os.getenv("ZOTERO_API_VERSION", DEFAULT_API_VERSION),
        default_limit=os.getenv("ZOTERO_DEFAULT_LIMIT", str(DEFAULT_LIMIT)),
        log_level=os.getenv("LOG_LEVEL", "WARNING"),
    )
