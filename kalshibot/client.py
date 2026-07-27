"""Kalshi API client factory."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from kalshi_python_sync import Configuration, KalshiClient

HOSTS = {
    "demo": "https://external-api.demo.kalshi.co/trade-api/v2",
    "prod": "https://external-api.kalshi.com/trade-api/v2",
}


def get_env_name() -> str:
    """Return configured Kalshi environment: demo or prod."""
    load_dotenv()
    env = (os.getenv("KALSHI_ENV") or "demo").strip().lower()
    if env not in HOSTS:
        raise ValueError(f"KALSHI_ENV must be 'demo' or 'prod', got {env!r}")
    return env


def load_response(resp: Any) -> dict:
    """Decode an SDK raw response body into a dict."""
    raw = resp.data.decode() if isinstance(resp.data, bytes) else resp.data
    return json.loads(raw)


def get_client() -> KalshiClient:
    """Build an authenticated Kalshi client from environment variables."""
    load_dotenv()

    api_key_id = os.getenv("KALSHI_API_KEY_ID")
    key_path = os.getenv("KALSHI_PRIVATE_KEY_PATH")
    env = get_env_name()

    if not api_key_id or api_key_id == "your-api-key-id":
        raise ValueError(
            "Set KALSHI_API_KEY_ID in .env (from Kalshi Account → API Keys)."
        )
    if not key_path:
        raise ValueError("Set KALSHI_PRIVATE_KEY_PATH in .env to your .pem file.")

    pem_path = Path(key_path).expanduser()
    if not pem_path.is_file():
        raise FileNotFoundError(f"Private key not found: {pem_path}")

    config = Configuration(host=HOSTS[env])
    config.api_key_id = api_key_id
    config.private_key_pem = pem_path.read_text()

    return KalshiClient(config)
