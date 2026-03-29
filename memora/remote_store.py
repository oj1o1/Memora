"""
Remote REST API store for Memora cloud mode.
Talks to a Vercel-hosted (or any) Memora API instead of local SQLite.
"""

import os
from typing import Optional, Union

import requests


class RemoteStore:
    """Drop-in replacement for DecisionStore that proxies to a remote Memora API."""

    def __init__(
        self,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.api_url = (api_url or os.getenv("MEMORA_API_URL", "")).rstrip("/")
        self.api_key = api_key or os.getenv("MEMORA_API_KEY", "")
        if not self.api_url:
            raise ValueError("MEMORA_API_URL is required for RemoteStore")

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def _url(self, path: str) -> str:
        return f"{self.api_url}{path}"

    def _handle(self, resp: requests.Response) -> Union[dict, list, None]:
        resp.raise_for_status()
        if resp.status_code == 204:
            return None
        return resp.json()

    @staticmethod
    def _unwrap(data: Union[dict, list]) -> list:
        """Unwrap paginated envelope {results, limit, offset} back to a plain list."""
        if isinstance(data, dict) and "results" in data:
            return data["results"]
        if isinstance(data, list):
            return data
        return []

    # ---- DecisionStore-compatible interface ----

    def save(
        self,
        summary: str,
        reasoning: str,
        alternatives: Optional[list[str]] = None,
        tags: Optional[list[str]] = None,
        context: str = "",
        project: str = "",
        agent: str = "",
        source: str = "manual",
        confidence: float = 1.0,
        decision_id: Optional[str] = None,
        type: str = "DECISION",
    ) -> dict:
        payload = {
            "summary": summary,
            "reasoning": reasoning,
            "alternatives": alternatives or [],
            "tags": tags or [],
            "context": context,
            "project": project,
            "agent": agent,
            "source": source,
            "confidence": confidence,
            "type": type,
        }
        if decision_id:
            payload["id"] = decision_id
        resp = requests.post(self._url("/api/decisions"), json=payload, headers=self._headers())
        return self._handle(resp)

    def get(self, decision_id: str) -> Optional[dict]:
        resp = requests.get(self._url(f"/api/decisions/{decision_id}"), headers=self._headers())
        if resp.status_code == 404:
            return None
        return self._handle(resp)

    def list_decisions(
        self,
        project: str = "",
        agent: str = "",
        tag: str = "",
        type: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        params = {"limit": limit, "offset": offset}
        if project:
            params["project"] = project
        if agent:
            params["agent"] = agent
        if tag:
            params["tag"] = tag
        if type:
            params["type"] = type
        resp = requests.get(self._url("/api/decisions"), params=params, headers=self._headers())
        return self._unwrap(self._handle(resp))

    def search(self, query: str, limit: int = 20) -> list[dict]:
        if not query.strip():
            return []
        resp = requests.get(
            self._url("/api/decisions/search"),
            params={"q": query, "limit": limit},
            headers=self._headers(),
        )
        return self._unwrap(self._handle(resp))

    def delete(self, decision_id: str) -> bool:
        resp = requests.delete(self._url(f"/api/decisions/{decision_id}"), headers=self._headers())
        if resp.status_code == 404:
            return False
        resp.raise_for_status()
        return True

    def link(self, from_id: str, to_id: str, relation: str = "related") -> dict:
        resp = requests.post(
            self._url("/api/decisions/link"),
            json={"from_id": from_id, "to_id": to_id, "relation": relation},
            headers=self._headers(),
        )
        return self._handle(resp)

    def get_links(self, decision_id: str) -> list[dict]:
        resp = requests.get(
            self._url(f"/api/decisions/{decision_id}/links"),
            headers=self._headers(),
        )
        return self._handle(resp)

    def stats(self, project: str = "") -> dict:
        params = {}
        if project:
            params["project"] = project
        resp = requests.get(self._url("/api/stats"), params=params, headers=self._headers())
        return self._handle(resp)

    def close(self):
        pass  # No persistent connection to close
