"""
SQLite-backed storage for Memora decisions.
Handles persistence, indexing, and full-text search.
"""

import sqlite3
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

VALID_TYPES = {
    "DECISION", "REJECTED", "NEXT", "BUG_FIXED", "CONTEXT",
    "ASSUMPTION", "TRADEOFF", "CONSTRAINT", "DEPENDENCY", "RISK",
}


def _default_db_path() -> str:
    env_path = os.getenv("MEMORA_DB_PATH")
    if env_path:
        return os.path.expanduser(env_path)
    # Default: ~/.memora/decisions.db (works on any OS)
    home_path = os.path.join(os.path.expanduser("~"), ".memora", "decisions.db")
    # If home drive has space, use it
    try:
        import shutil
        home_dir = os.path.expanduser("~")
        free = shutil.disk_usage(home_dir).free
        if free > 10 * 1024 * 1024:  # >10MB free
            return home_path
    except Exception:
        return home_path
    # Fallback: store next to the package itself
    fallback = os.path.join(Path(__file__).parent.parent, ".memora", "decisions.db")
    return fallback


class DecisionStore:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or _default_db_path()
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._migrate()

    def _migrate(self):
        cur = self._conn.cursor()
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS decisions (
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
                workspace_id TEXT NOT NULL DEFAULT 'local',
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS decision_links (
                id          TEXT PRIMARY KEY,
                from_id     TEXT NOT NULL REFERENCES decisions(id) ON DELETE CASCADE,
                to_id       TEXT NOT NULL REFERENCES decisions(id) ON DELETE CASCADE,
                relation    TEXT NOT NULL DEFAULT 'related',
                created_at  TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_decisions_project ON decisions(project);
            CREATE INDEX IF NOT EXISTS idx_decisions_agent ON decisions(agent);
            CREATE INDEX IF NOT EXISTS idx_decisions_type ON decisions(type);
            CREATE INDEX IF NOT EXISTS idx_decisions_created ON decisions(created_at);
            CREATE INDEX IF NOT EXISTS idx_links_from ON decision_links(from_id);
            CREATE INDEX IF NOT EXISTS idx_links_to ON decision_links(to_id);
        """)

        # Migration: add type column to existing databases
        cols = {row[1] for row in cur.execute("PRAGMA table_info(decisions)").fetchall()}
        if "type" not in cols:
            cur.execute("ALTER TABLE decisions ADD COLUMN type TEXT NOT NULL DEFAULT 'DECISION'")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_decisions_type ON decisions(type)")

        # Migration: add workspace_id column
        if "workspace_id" not in cols:
            cur.execute("ALTER TABLE decisions ADD COLUMN workspace_id TEXT NOT NULL DEFAULT 'local'")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_decisions_workspace ON decisions(workspace_id)")

        cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='decisions_fts'")
        fts_row = cur.fetchone()
        needs_fts_rebuild = False
        if fts_row is not None:
            # Check if existing FTS table includes the type column
            if "type" not in fts_row[0]:
                cur.executescript("""
                    DROP TRIGGER IF EXISTS decisions_ai;
                    DROP TRIGGER IF EXISTS decisions_ad;
                    DROP TRIGGER IF EXISTS decisions_au;
                    DROP TABLE decisions_fts;
                """)
                needs_fts_rebuild = True

        if fts_row is None or needs_fts_rebuild:
            cur.executescript("""
                CREATE VIRTUAL TABLE decisions_fts USING fts5(
                    id UNINDEXED,
                    type,
                    summary,
                    reasoning,
                    alternatives,
                    tags,
                    context,
                    content='decisions',
                    content_rowid='rowid'
                );

                CREATE TRIGGER IF NOT EXISTS decisions_ai AFTER INSERT ON decisions BEGIN
                    INSERT INTO decisions_fts(rowid, id, type, summary, reasoning, alternatives, tags, context)
                    VALUES (new.rowid, new.id, new.type, new.summary, new.reasoning, new.alternatives, new.tags, new.context);
                END;

                CREATE TRIGGER IF NOT EXISTS decisions_ad AFTER DELETE ON decisions BEGIN
                    INSERT INTO decisions_fts(decisions_fts, rowid, id, type, summary, reasoning, alternatives, tags, context)
                    VALUES ('delete', old.rowid, old.id, old.type, old.summary, old.reasoning, old.alternatives, old.tags, old.context);
                END;

                CREATE TRIGGER IF NOT EXISTS decisions_au AFTER UPDATE ON decisions BEGIN
                    INSERT INTO decisions_fts(decisions_fts, rowid, id, type, summary, reasoning, alternatives, tags, context)
                    VALUES ('delete', old.rowid, old.id, old.type, old.summary, old.reasoning, old.alternatives, old.tags, old.context);
                    INSERT INTO decisions_fts(rowid, id, type, summary, reasoning, alternatives, tags, context)
                    VALUES (new.rowid, new.id, new.type, new.summary, new.reasoning, new.alternatives, new.tags, new.context);
                END;
            """)

            if needs_fts_rebuild:
                cur.execute("INSERT INTO decisions_fts(decisions_fts) VALUES('rebuild')")

        self._conn.commit()

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

        self._conn.execute(
            """INSERT INTO decisions (id, type, summary, reasoning, alternatives, tags, context, project, agent, source, confidence, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                 type=excluded.type, summary=excluded.summary, reasoning=excluded.reasoning,
                 alternatives=excluded.alternatives, tags=excluded.tags,
                 context=excluded.context, project=excluded.project,
                 agent=excluded.agent, source=excluded.source,
                 confidence=excluded.confidence, updated_at=excluded.updated_at""",
            (did, type, summary, reasoning, alts, tag_json, context, project, agent, source, confidence, now, now),
        )
        self._conn.commit()
        return self.get(did)

    def get(self, decision_id: str) -> Optional[dict]:
        row = self._conn.execute("SELECT * FROM decisions WHERE id = ?", (decision_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

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
        params: list = []
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
        rows = self._conn.execute(
            f"SELECT * FROM decisions{where} ORDER BY created_at DESC LIMIT ? OFFSET ?", params
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def search(self, query: str, limit: int = 20) -> list[dict]:
        fts_query = " OR ".join(f'"{w}"' for w in query.strip().split() if w)
        if not fts_query:
            return []
        rows = self._conn.execute(
            """SELECT d.* FROM decisions d
               JOIN decisions_fts f ON d.id = f.id
               WHERE decisions_fts MATCH ?
               ORDER BY rank
               LIMIT ?""",
            (fts_query, limit),
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def delete(self, decision_id: str) -> bool:
        cur = self._conn.execute("DELETE FROM decisions WHERE id = ?", (decision_id,))
        self._conn.commit()
        return cur.rowcount > 0

    def link(self, from_id: str, to_id: str, relation: str = "related") -> dict:
        now = datetime.now(timezone.utc).isoformat()
        lid = uuid.uuid4().hex[:12]
        self._conn.execute(
            "INSERT INTO decision_links (id, from_id, to_id, relation, created_at) VALUES (?, ?, ?, ?, ?)",
            (lid, from_id, to_id, relation, now),
        )
        self._conn.commit()
        return {"id": lid, "from_id": from_id, "to_id": to_id, "relation": relation, "created_at": now}

    def get_links(self, decision_id: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM decision_links WHERE from_id = ? OR to_id = ?", (decision_id, decision_id)
        ).fetchall()
        return [dict(r) for r in rows]

    def stats(self, project: str = "") -> dict:
        params: list = []
        where = ""
        if project:
            where = " WHERE project = ?"
            params = [project]
        row = self._conn.execute(f"SELECT COUNT(*) as cnt FROM decisions{where}", params).fetchone()
        total = row["cnt"]

        tag_rows = self._conn.execute(
            f"SELECT tags FROM decisions{where}", params
        ).fetchall()
        tag_counts: dict[str, int] = {}
        for r in tag_rows:
            for t in json.loads(r["tags"]):
                tag_counts[t] = tag_counts.get(t, 0) + 1

        source_rows = self._conn.execute(
            f"SELECT source, COUNT(*) as cnt FROM decisions{where} GROUP BY source", params
        ).fetchall()
        sources = {r["source"]: r["cnt"] for r in source_rows}

        type_rows = self._conn.execute(
            f"SELECT type, COUNT(*) as cnt FROM decisions{where} GROUP BY type", params
        ).fetchall()
        types = {r["type"]: r["cnt"] for r in type_rows}

        return {"total": total, "tags": tag_counts, "sources": sources, "types": types}

    def _row_to_dict(self, row: sqlite3.Row) -> dict:
        d = dict(row)
        d["alternatives"] = json.loads(d["alternatives"])
        d["tags"] = json.loads(d["tags"])
        return d

    def close(self):
        self._conn.close()


# Alias for hybrid architecture — LocalStore IS DecisionStore
LocalStore = DecisionStore
