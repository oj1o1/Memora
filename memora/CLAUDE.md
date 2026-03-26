# Memora

Decision memory layer for AI agent builders. Captures WHY decisions were made during development.

## Project Structure

- `store.py` — SQLite storage with FTS5 full-text search
- `extractor.py` — AI-powered decision extraction using Claude
- `memory.py` — High-level memory API (main interface for all consumers)
- `server.py` — FastMCP server exposing Memora as MCP tools
- `app.py` — Flask web API + dashboard server
- `cli.py` — CLI using Click + Rich
- `cursor_hook.py` — Cursor IDE integration
- `antigravity_adapter.py` — Adapter for agent frameworks
- `git_hook.py` — Post-commit hook for automatic decision extraction
- `dashboard/index.html` — Single-page web dashboard

## Running

```bash
pip install -r requirements.txt
python -m memora.cli --help          # CLI
python -m memora.server              # MCP server
python -m memora.app                 # Web dashboard on :8377
python -m memora.git_hook install    # Install git hook
python -m memora.cursor_hook install # Install Cursor rules
```

## Key Design Decisions

- SQLite with WAL mode for single-file, zero-config storage
- FTS5 for fast full-text search across all decision fields
- Lazy initialization of the Anthropic client (only needed for extraction)
- MCP server uses FastMCP for tool registration
- All modules share the same MemoraMemory interface
- Decisions have: summary, reasoning, alternatives, tags, context, project, agent, source, confidence
