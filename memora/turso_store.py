"""
Turso (libSQL) cloud store for Memora.
Structure identical to LocalStore/DecisionStore but uses libsql-client.

Activate by setting MEMORA_CLOUD_MODE=true (and providing TURSO_DATABASE_URL / TURSO_AUTH_TOKEN).
This is a future compatibility layer — not enabled by default.
"""

import os
from typing import Optional


class TursoStore:
    """Cloud-native SQLite store backed by Turso/libSQL.

    Implements the same interface as DecisionStore so it can be used
    as a drop-in replacement via memory_backend.get_store().
    """

    def __init__(self):
        self.database_url = os.getenv("TURSO_DATABASE_URL", "")
        self.auth_token = os.getenv("TURSO_AUTH_TOKEN", "")
        if not self.database_url:
            raise ValueError(
                "TURSO_DATABASE_URL is required when MEMORA_CLOUD_MODE=true. "
                "Get one at https://turso.tech"
            )
        self._client = None
        self._connect()

    def _connect(self):
        try:
            import libsql_experimental as libsql
        except ImportError:
            raise ImportError(
                "libsql-experimental is required for Turso support. "
                "Install with: pip install libsql-experimental"
            )
        self._client = libsql.connect(
            self.database_url,
            auth_token=self.auth_token,
        )
        self._migrate()

    def _migrate(self):
        # TODO: Run the same schema as LocalStore against Turso
        raise NotImplementedError(
            "TursoStore is a future compatibility layer. "
            "Full implementation coming soon."
        )

    def save(self, **kwargs) -> dict:
        raise NotImplementedError("TursoStore not yet implemented")

    def get(self, decision_id: str) -> Optional[dict]:
        raise NotImplementedError("TursoStore not yet implemented")

    def list_decisions(self, **kwargs) -> list[dict]:
        raise NotImplementedError("TursoStore not yet implemented")

    def search(self, query: str, limit: int = 20) -> list[dict]:
        raise NotImplementedError("TursoStore not yet implemented")

    def delete(self, decision_id: str) -> bool:
        raise NotImplementedError("TursoStore not yet implemented")

    def link(self, from_id: str, to_id: str, relation: str = "related") -> dict:
        raise NotImplementedError("TursoStore not yet implemented")

    def get_links(self, decision_id: str) -> list[dict]:
        raise NotImplementedError("TursoStore not yet implemented")

    def stats(self, project: str = "") -> dict:
        raise NotImplementedError("TursoStore not yet implemented")

    def close(self):
        if self._client:
            self._client.close()
