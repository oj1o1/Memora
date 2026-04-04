"""
Turso (libSQL) cloud store for Memora.
Uses Turso's HTTP API via requests — no native binary dependencies.
Works in Vercel serverless, local dev, and any Python environment.

Activate by setting MEMORA_CLOUD_MODE=true and providing:
  TURSO_DATABASE_URL  — e.g. libsql://your-db-name.turso.io
  TURSO_AUTH_TOKEN    — from `turso db tokens create`
"""

import json
import os
import uuid
import requests
from datetime import datetime, timezone
from typing import Optional

from memora.store import VALID_TYPES


class TursoStore:
    """Cloud-native SQLite store backed by Turso/libSQL over HTTP."""

    def __init__(self):
        self.database_url = os.getenv("TURSO_DATABASE_URL", "")
        self.auth_token = os.getenv("TURSO_AUTH_TOKEN", "")
        if not self.database_url:
            raise ValueError(
                "TURSO_DATABASE_URL is required when MEMORA_CLOUD_MODE=true. "
                "Get one at https://turso.tech"
            )
        # Convert libsql:// to https:// for HTTP API
        self._http_url = self.database_url.replace("libsql://", "https://")
        if not self._http_url.startswith("https://"):
            self._http_url = "https://" + self._http_url
        self._http_url = self._http_url.rstrip("/")
        self._migrate()

    def _execute(self, sql: str, args=None):
        """Execute a single SQL statement via Turso HTTP API."""
        stmt = {"type": "execute", "stmt": {"sql": sql}}
        if args:
            stmt["stmt"]["args"] = [
                {"type": "null", "value": None} if v is None
                else {"type": "integer", "value": str(v)} if isinstance(v, int)
                else {"type": "float", "value": v} if isinstance(v, float)
                else {"type": "text", "value": str(v)}
                for v in args
            ]
        return self._request([stmt])

    def _execute_batch(self, statements: list):
        """Execute multiple SQL statements in a batch."""
        stmts = []
        for sql, args in statements:
            stmt = {"type": "execute", "stmt": {"sql": sql}}
            if args:
                stmt["stmt"]["args"] = [
                    {"type": "null", "value": None} if v is None
                    else {"type": "integer", "value": str(v)} if isinstance(v, int)
                    else {"type": "float", "value": v} if isinstance(v, float)
                    else {"type": "text", "value": str(v)}
                    for v in args
                ]
            stmts.append(stmt)
        return self._request(stmts)

    def _request(self, statements: list):
        """Send a pipeline request to Turso HTTP API."""
        url = f"{self._http_url}/v3/pipeline"
        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        body = {"requests": statements + [{"type": "close"}]}
        resp = requests.post(url, json=body, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        results = []
        for r in data.get("results", []):
            if r.get("type") == "error":
                error = r.get("error", {})
                raise RuntimeError(f"Turso error: {error.get('message', str(error))}")
            if r.get("type") == "ok":
                results.append(r.get("response", {}))
        return results

    def _rows_to_dicts(self, response: dict) -> list[dict]:
        """Convert Turso HTTP API response to list of dicts."""
        result = response.get("result", {})
        cols = [c["name"] for c in result.get("cols", [])]
        rows = result.get("rows", [])
        dicts = []
        for row in rows:
            d = {}
            for i, col in enumerate(cols):
                val = row[i].get("value")
                d[col] = val
            dicts.append(d)
        return dicts

    def _parse_decision(self, d: dict) -> dict:
        """Parse a raw row dict into a proper decision dict."""
        d["alternatives"] = json.loads(d.get("alternatives") or "[]")
        d["tags"] = json.loads(d.get("tags") or "[]")
        d["confidence"] = float(d.get("confidence", 1.0))
        return d

    def _migrate(self):
        """Create tables if they don't exist."""
        stmts = [
            ("""CREATE TABLE IF NOT EXISTS decisions (
                id          TEXT PRIMARY KEY,
                type        TEXT NOT NULL DEFAULT 'DECISION',
                summary     TEXT NOT NULL,
                reasoning   TEXT NOT NULL,
                alternatives TEXT NOT NULL DEFAULT '[]',
                tags        TEXT NOT NULL DEFAULT '[]',
                context     TEXT NOT NULL DEFAULT '',
                project     TEXT NOT NULL DEFAULT '',
                agent       TEXT NOT NULL DEFAULT '',
                source      TEXT NOT NULL DEFAULT 'manual',
                confidence  REAL NOT NULL DEFAULT 1.0,
                workspace_id TEXT NOT NULL DEFAULT 'cloud',
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            )""", None),
            ("""CREATE TABLE IF NOT EXISTS decision_links (
                id          TEXT PRIMARY KEY,
                from_id     TEXT NOT NULL,
                to_id       TEXT NOT NULL,
                relation    TEXT NOT NULL DEFAULT 'related',
                created_at  TEXT NOT NULL
            )""", None),
            ("CREATE INDEX IF NOT EXISTS idx_decisions_type ON decisions(type)", None),
            ("CREATE INDEX IF NOT EXISTS idx_decisions_project ON decisions(project)", None),
            ("CREATE INDEX IF NOT EXISTS idx_decisions_created ON decisions(created_at)", None),
        ]
        self._execute_batch(stmts)

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
        if type not in VALID_TYPES:
            type = "DECISION"
        now = datetime.now(timezone.utc).isoformat()
        did = decision_id or uuid.uuid4().hex[:12]
        alts = json.dumps(alternatives or [])
        tag_json = json.dumps(tags or [])

        self._execute(
            """INSERT OR REPLACE INTO decisions
               (id, type, summary, reasoning, alternatives, tags, context,
                project, agent, source, confidence, workspace_id, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [did, type, summary, reasoning, alts, tag_json, context,
             project, agent, source, confidence, "cloud", now, now],
        )
        return self.get(did)

    def get(self, decision_id: str) -> Optional[dict]:
        results = self._execute(
            "SELECT * FROM decisions WHERE id = ?", [decision_id]
        )
        rows = self._rows_to_dicts(results[0])
        if not rows:
            return None
        return self._parse_decision(rows[0])

    def list_decisions(
        self,
        project: str = "",
        agent: str = "",
        tag: str = "",
        type: str = "",
        limit: int = 50,
        offset: int = 0,
        workspace: str = "",
    ) -> list[dict]:
        clauses = []
        params = []
        if project:
            clauses.append("project = ?")
            params.append(project)
        if agent:
            clauses.append("agent = ?")
            params.append(agent)
        if tag:
            clauses.append("tags LIKE ?")
            params.append(f'%"{tag}"%')
        if type:
            clauses.append("type = ?")
            params.append(type.upper())
        if workspace:
            clauses.append("workspace_id = ?")
            params.append(workspace)

        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        params.extend([limit, offset])
        results = self._execute(
            f"SELECT * FROM decisions{where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params,
        )
        rows = self._rows_to_dicts(results[0])
        return [self._parse_decision(r) for r in rows]

    def search(self, query: str, limit: int = 20) -> list[dict]:
        # Turso doesn't support FTS5 reliably, use LIKE-based search
        words = [w.strip() for w in query.strip().split() if w.strip()]
        if not words:
            return []
        clauses = []
        params = []
        for w in words:
            clauses.append(
                "(summary LIKE ? OR reasoning LIKE ? OR tags LIKE ? OR type LIKE ?)"
            )
            like = f"%{w}%"
            params.extend([like, like, like, like])

        where = " OR ".join(clauses)
        params.append(limit)
        results = self._execute(
            f"SELECT * FROM decisions WHERE {where} ORDER BY created_at DESC LIMIT ?",
            params,
        )
        rows = self._rows_to_dicts(results[0])
        return [self._parse_decision(r) for r in rows]

    def delete(self, decision_id: str) -> bool:
        results = self._execute(
            "DELETE FROM decisions WHERE id = ?", [decision_id]
        )
        affected = results[0].get("result", {}).get("affected_row_count", 0)
        return affected > 0

    def link(self, from_id: str, to_id: str, relation: str = "related") -> dict:
        now = datetime.now(timezone.utc).isoformat()
        lid = uuid.uuid4().hex[:12]
        self._execute(
            "INSERT INTO decision_links (id, from_id, to_id, relation, created_at) VALUES (?, ?, ?, ?, ?)",
            [lid, from_id, to_id, relation, now],
        )
        return {"id": lid, "from_id": from_id, "to_id": to_id, "relation": relation, "created_at": now}

    def get_links(self, decision_id: str) -> list[dict]:
        results = self._execute(
            "SELECT * FROM decision_links WHERE from_id = ? OR to_id = ?",
            [decision_id, decision_id],
        )
        return self._rows_to_dicts(results[0])

    def stats(self, project: str = "") -> dict:
        params = []
        where = ""
        if project:
            where = " WHERE project = ?"
            params = [project]

        stmts = [
            (f"SELECT COUNT(*) as cnt FROM decisions{where}", params),
            (f"SELECT tags FROM decisions{where}", params),
            (f"SELECT source, COUNT(*) as cnt FROM decisions{where} GROUP BY source", params),
            (f"SELECT type, COUNT(*) as cnt FROM decisions{where} GROUP BY type", params),
        ]
        results = self._execute_batch(stmts)

        total_rows = self._rows_to_dicts(results[0])
        total = int(total_rows[0]["cnt"]) if total_rows else 0

        tag_rows = self._rows_to_dicts(results[1])
        tag_counts = {}
        for r in tag_rows:
            for t in json.loads(r.get("tags") or "[]"):
                tag_counts[t] = tag_counts.get(t, 0) + 1

        source_rows = self._rows_to_dicts(results[2])
        sources = {r["source"]: int(r["cnt"]) for r in source_rows}

        type_rows = self._rows_to_dicts(results[3])
        types = {r["type"]: int(r["cnt"]) for r in type_rows}

        return {"total": total, "tags": tag_counts, "sources": sources, "types": types}

    def close(self):
        pass  # HTTP client — no persistent connection to close
