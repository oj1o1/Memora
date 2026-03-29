# Memora

Decision memory infrastructure for AI agent builders. Records WHY decisions were made during agent construction.

## Project Structure

- `store.py` — SQLite storage with FTS5 full-text search, workspace support
- `remote_store.py` — REST API client for cloud workspace mode (RemoteStore)
- `turso_store.py` — Turso libSQL cloud storage (TursoStore)
- `memory_backend.py` — Backend selector: routes to LocalStore / RemoteStore / TursoStore
- `memory.py` — High-level memory API (main interface for all consumers)
- `extractor.py` — AI-powered decision extraction using Groq
- `server.py` — FastMCP server exposing Memora as MCP tools
- `app.py` — Flask web API + dashboard server with rate limiting and pagination
- `cli.py` — CLI using Click + Rich
- `antigravity_adapter.py` — Adapter for agent frameworks
- `api_limits.py` — Pagination constants, rate limiter, request safeguards
- `cursor_hook.py` — Cursor IDE integration
- `git_hook.py` — Post-commit hook for automatic decision extraction
- `dashboard/index.html` — Local single-page web dashboard
- `landing/index.html` — Landing page

## Running

```bash
pip install -e .[all]
memora --help                # CLI
python -m memora.server      # MCP server
python -m memora.app         # Web dashboard on :8377
```

## Backend Modes

- Default → LocalStore (SQLite at ~/.memora/decisions.db)
- `MEMORA_API_URL` set → RemoteStore (REST API)
- `MEMORA_CLOUD_MODE=true` or Vercel env → TursoStore (libSQL)

## Key Design Decisions

- SQLite with WAL mode for single-file, zero-config local storage
- FTS5 for fast full-text search across all decision fields
- Groq (llama-3.3-70b-versatile) for AI extraction
- MCP server uses FastMCP for tool registration
- All consumers go through MemoraMemory → memory_backend.py → store
- Auto-loads ~/.memora/config.json into env vars at startup
- Auth only enforced when MEMORA_API_KEY is set
- 10 decision types: DECISION, REJECTED, NEXT, BUG_FIXED, CONTEXT, ASSUMPTION, TRADEOFF, CONSTRAINT, DEPENDENCY, RISK
- API endpoints return paginated envelopes: {results, limit, offset, count}
