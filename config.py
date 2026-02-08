"""
Configuration management for Halo MCP Server.
Loads tokens from config.json or environment variables.
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path

_CONFIG_DIR = Path(__file__).parent
_CONFIG_FILE = _CONFIG_DIR / "config.json"


@dataclass(frozen=True)
class HaloConfig:
    """Immutable configuration for Halo API access."""
    auth_token: str
    context_token: str
    transaction_id: str


_cached_config: HaloConfig | None = None


def get_config() -> HaloConfig:
    """
    Load configuration from config.json or environment variables.
    Cached after first load.

    Environment variable fallbacks:
        HALO_AUTH_TOKEN, HALO_CONTEXT_TOKEN, HALO_TRANSACTION_ID
    """
    global _cached_config
    if _cached_config is not None:
        return _cached_config

    auth_token = None
    context_token = None
    transaction_id = ""

    if _CONFIG_FILE.exists():
        with open(_CONFIG_FILE) as f:
            data = json.load(f)
        auth_token = data.get("authToken")
        context_token = data.get("contextToken")
        transaction_id = data.get("transactionId", "")

    # Environment variables override / fallback
    auth_token = os.environ.get("HALO_AUTH_TOKEN", auth_token)
    context_token = os.environ.get("HALO_CONTEXT_TOKEN", context_token)
    transaction_id = os.environ.get("HALO_TRANSACTION_ID", transaction_id or "")

    if not auth_token:
        raise ValueError(
            "No auth token found. Set HALO_AUTH_TOKEN env var or create HaloMCP/config.json"
        )
    if not context_token:
        context_token = auth_token

    _cached_config = HaloConfig(
        auth_token=auth_token,
        context_token=context_token,
        transaction_id=transaction_id,
    )
    return _cached_config


def reload_config() -> HaloConfig:
    """Force reload configuration (useful if tokens are refreshed)."""
    global _cached_config
    _cached_config = None
    return get_config()
