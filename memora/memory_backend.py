"""
Backend selector for Memora storage.

Automatically chooses the right store implementation based on environment:
  - MEMORA_API_URL set        -> RemoteStore  (cloud mode via REST API)
  - MEMORA_CLOUD_MODE=true    -> TursoStore   (cloud-native SQLite)
  - VERCEL env var detected   -> TursoStore   (auto-enable on Vercel)
  - otherwise                 -> LocalStore   (local SQLite, default)
"""

import os
from typing import Optional


def _load_config():
    """Load saved config from ~/.memora/config.json into environment if not already set."""
    import json
    from pathlib import Path

    config_path = Path.home() / ".memora" / "config.json"
    if not config_path.exists():
        return
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        for key in ("MEMORA_API_URL", "MEMORA_API_KEY"):
            if key in config and not os.getenv(key):
                os.environ[key] = config[key]
    except Exception:
        pass  # Config is optional -- don't crash on malformed JSON


def _is_vercel() -> bool:
    """Detect if running inside a Vercel serverless function."""
    return bool(os.getenv("VERCEL") or os.getenv("VERCEL_ENV"))


def get_backend_mode() -> str:
    """Return the current backend mode as a string."""
    _load_config()

    if os.getenv("MEMORA_API_URL"):
        return "REMOTE"

    cloud_mode = os.getenv("MEMORA_CLOUD_MODE", "").lower() in ("true", "1", "yes")
    if cloud_mode or _is_vercel():
        return "TURSO"

    return "LOCAL"


def get_store(db_path: Optional[str] = None):
    """Return the appropriate store backend.

    Args:
        db_path: Explicit SQLite path. If provided, always returns LocalStore.

    Returns:
        A store instance (LocalStore, RemoteStore, or TursoStore).
    """
    _load_config()

    # Explicit db_path always means local
    if db_path:
        from memora.store import LocalStore
        return LocalStore(db_path=db_path)

    api_url = os.getenv("MEMORA_API_URL")
    if api_url:
        from memora.remote_store import RemoteStore
        return RemoteStore(api_url=api_url, api_key=os.getenv("MEMORA_API_KEY"))

    cloud_mode = os.getenv("MEMORA_CLOUD_MODE", "").lower() in ("true", "1", "yes")
    if cloud_mode or _is_vercel():
        from memora.turso_store import TursoStore
        return TursoStore()

    from memora.store import LocalStore
    return LocalStore(db_path=db_path)
