<<<<<<< HEAD
# Memora

**Decision memory infrastructure for AI agent builders.**

Memora records why an agent behaves the way it does — while it is being built, not after deployment.

---

## The Problem

Most agent bugs are not in the code. They come from forgotten decisions made during development.

A prompt was reworded. A tool was swapped out. A confidence threshold was raised. A retrieval strategy changed. A fallback was removed. The agent broke — and no one remembers why the original choice was made.

These decisions live in chat logs, PR descriptions, and the heads of engineers. When something breaks weeks later, the team reverse-engineers intent from code that was never designed to explain itself.

Memora fixes this. It records engineering decisions — the summary, the reasoning, the alternatives considered, and the context — as structured, searchable memory. Locally by default, synced to a shared workspace when needed.

**Memora turns agent explanations from generated guesses into retrieved engineering intent.**

---

## What Memora Is Not

| | Memora |
|---|---|
| **Chat memory** | No. Memora does not store conversation history. |
| **Vector database** | No. Memora uses FTS5 full-text search, not embeddings. |
| **Observability tool** | No. Memora captures pre-deployment reasoning, not runtime traces. |
| **Evaluation framework** | No. Memora records why a decision was made, not whether it was correct. |

Hallucinations explain what an agent *might* be doing. Memora records what engineers *actually decided* while building it.

---

## Features

- **Local-first reasoning memory** — SQLite with WAL mode, zero-config
- **Cloud workspace sync** — RemoteStore connects local CLI to a hosted API
- **Turso-backed persistence** — cloud-native libSQL for Vercel deployments
- **Workspace-aware decision timeline** — filter and isolate decisions by workspace
- **Dashboard viewer** — single-page web UI for browsing and searching decisions
- **MCP integration** — expose Memora as tools in Claude Code and Cursor
- **Antigravity adapter** — drop-in integration for agent frameworks
- **Typed reasoning schema** — 10 decision types: `DECISION`, `REJECTED`, `NEXT`, `BUG_FIXED`, `CONTEXT`, `ASSUMPTION`, `TRADEOFF`, `CONSTRAINT`, `DEPENDENCY`, `RISK`
- **Automatic backend switching** — environment variables control storage routing
- **API safeguards** — pagination, rate limiting, request size protection

---

## Architecture

Memora operates in three modes, selected automatically based on environment configuration:

```
CLI / MCP / Adapter / Dashboard
            │
    Memora backend selector
            │
  ┌─────────┼─────────┐
  │         │         │
LocalStore  RemoteStore  TursoStore
(SQLite)    (REST API)   (libSQL)
```

| Mode | Trigger | Storage |
|------|---------|---------|
| **Local** | Default (no env vars) | SQLite at `~/.memora/decisions.db` |
| **Remote** | `MEMORA_API_URL` is set | REST API (e.g. Vercel-hosted Memora) |
| **Turso** | `MEMORA_CLOUD_MODE=true` or `VERCEL` env detected | Turso libSQL cloud database |

The backend selector (`memora/memory_backend.py`) routes all storage calls. Consumers — CLI, MCP server, adapter, dashboard — never interact with storage directly.

---

## Installation

From PyPI:

```bash
pip install memora
```

From source:

```bash
pip install git+https://github.com/anthropics/Memora.git
```

With all optional dependencies (MCP, web dashboard, AI extraction):

```bash
pip install memora[all]
```

Individual extras: `web`, `mcp`, `extract`, `turso`.

Requires Python 3.9+.

---

## Quick Start

### Record a decision

```python
from memora.antigravity_adapter import record_decision

record_decision(
    decision="Use PostgreSQL for metadata store",
    reason="Need JSONB support for flexible schema evolution",
    alternatives=["SQLite", "DynamoDB"],
    tags=["database", "infrastructure"],
)
```

### Search past decisions

```python
from memora.antigravity_adapter import ask_memory

results = ask_memory("database choice")
for d in results:
    print(f"[{d['type']}] {d['summary']}: {d['reasoning']}")
```

### Record from CLI

```bash
memora record "Use PostgreSQL" \
  --reasoning "Need JSONB support for flexible schema" \
  --type DECISION \
  --tags database \
  --project my-agent
```

---

## CLI Usage

```bash
memora --help              # Show all commands
memora record SUMMARY      # Record a decision
memora search QUERY        # Full-text search
memora list                # List all decisions
memora show ID             # Show decision details
memora delete ID           # Delete a decision
memora link ID1 ID2        # Link related decisions
memora extract TEXT        # AI-extract decisions from text
memora stats               # Storage statistics

memora dashboard           # Open web dashboard
memora serve               # Start API server
memora mode                # Show current backend mode

memora login               # Connect to cloud workspace
memora logout              # Disconnect from cloud
memora doctor              # Run health checks
memora demo                # Interactive walkthrough
```

### Backend switching from CLI

`memora mode` displays the active backend, workspace, and database path. The backend switches automatically:

- No config → **LOCAL** (SQLite)
- After `memora login` → **REMOTE** (cloud API)
- On Vercel → **TURSO** (libSQL)

---

## Dashboard

### Local dashboard

```bash
memora dashboard
# Opens http://127.0.0.1:8377/dashboard
```

Or start the server directly:

```bash
python -m memora.app
```

### Cloud dashboard

Deploy to Vercel and access at:

```
https://your-app.vercel.app/dashboard
```

### Dashboard badges

The sidebar header displays two badges:

- **Backend badge** — `LOCAL`, `REMOTE`, or `TURSO` — shows which storage backend is active
- **Workspace badge** — shows the current workspace identifier

A workspace dropdown lets you filter decisions by workspace.

---

## Cloud Workspace Mode

Connect your local Memora to a shared cloud workspace:

```bash
memora login
```

This prompts for your API URL and key, then writes `~/.memora/config.json`:

```json
{
  "MEMORA_API_URL": "https://your-memora.vercel.app",
  "MEMORA_API_KEY": "your-api-key"
}
```

All entry points (CLI, MCP server, adapter) auto-load this config. Once connected:

- Decisions sync to the remote API
- Multiple engineers share the same reasoning timeline
- Multiple agents contribute to one workspace
- `memora logout` removes the config and switches back to local mode

Think of it like Git vs GitHub: local mode is your local repo, cloud workspace mode is the shared remote.

---

## MCP Integration

Memora exposes itself as an [MCP](https://modelcontextprotocol.io/) server, making reasoning memory available as tools in Claude Code and Cursor.

### Configuration

Add to your MCP config (`.mcp.json`, Claude Code settings, or Cursor config):

```json
{
  "mcpServers": {
    "memora": {
      "command": "python",
      "args": ["-m", "memora.server"]
    }
  }
}
```

### Available MCP tools

| Tool | Description |
|------|-------------|
| `record_decision` | Record a decision with reasoning, alternatives, tags |
| `recall_decisions` | Full-text search across all decisions |
| `get_decision` | Retrieve a specific decision by ID |
| `list_decisions` | List decisions with filters (project, agent, type) |
| `extract_decisions` | AI-extract decisions from a block of text |
| `link_decisions` | Link two related decisions |
| `get_related_decisions` | Get decisions linked to a given ID |
| `delete_decision` | Delete a decision |
| `decision_stats` | Get storage statistics |

Once configured, your AI assistant can retrieve past reasoning automatically during development sessions.

---

## Antigravity Adapter

For agent frameworks that don't use MCP, Memora provides a direct Python adapter.

### Simple API (module-level functions)

```python
from memora.antigravity_adapter import record_decision, ask_memory

# Record
record_decision(
    decision="Switched to BM25 retrieval",
    reason="Semantic similarity was failing on short queries",
    agent="SearchAgent",
    alternatives=["hybrid search", "keyword fallback"],
)

# Query
results = ask_memory("retrieval strategy")
```

### Class-based API (more control)

```python
from memora.antigravity_adapter import MemoraAdapter

adapter = MemoraAdapter(project="my-agent", agent="RefundAgent")

# Record decisions
adapter.on_decision("Use PostgreSQL", reasoning="Need JSONB support")

# Auto-extract decisions from agent messages
adapter.on_message("assistant", "I decided to switch to streaming responses because...")

# Process full conversation
adapter.on_conversation_end(messages)

# Search
results = adapter.query("database choice")

# Get formatted context for prompt injection
context = adapter.get_context("retrieval strategy")

# Get tool definitions for framework registration
tools = adapter.get_tool_definitions()
```

### Framework integration

The adapter provides `get_tool_definitions()` and `handle_tool_call()` for registering Memora as agent tools in any framework:

```python
adapter = MemoraAdapter(project="my-agent")

# Register tools with your framework
for tool in adapter.get_tool_definitions():
    framework.register_tool(tool)

# Handle calls
result = adapter.handle_tool_call(tool_name, tool_input)
```

---

## Backend Switching

Memora selects its storage backend automatically based on environment variables. No code changes needed.

```
┌─────────────────────────────────────────────────────┐
│ Priority 1: MEMORA_API_URL set?                     │
│   → RemoteStore (REST API to hosted Memora)         │
├─────────────────────────────────────────────────────┤
│ Priority 2: MEMORA_CLOUD_MODE=true or VERCEL env?   │
│   → TursoStore (libSQL cloud database)              │
├─────────────────────────────────────────────────────┤
│ Default: nothing set                                │
│   → LocalStore (SQLite at ~/.memora/decisions.db)   │
└─────────────────────────────────────────────────────┘
```

If you pass an explicit `db_path`, it always uses LocalStore regardless of environment.

### Environment variables

| Variable | Effect |
|----------|--------|
| `MEMORA_API_URL` | Activates RemoteStore — points to hosted API |
| `MEMORA_API_KEY` | Bearer token for authenticated API access |
| `MEMORA_CLOUD_MODE` | Set to `true` to activate TursoStore |
| `MEMORA_DB_PATH` | Override local SQLite database path |
| `MEMORA_WORKSPACE` | Workspace identifier for multi-tenant isolation |
| `MEMORA_HOST` | Flask server bind address (default: `127.0.0.1`) |
| `MEMORA_PORT` | Flask server port (default: `8377`) |
| `GROQ_API_KEY` | API key for AI-powered decision extraction |
| `TURSO_DATABASE_URL` | Turso database URL (for TursoStore) |
| `TURSO_AUTH_TOKEN` | Turso auth token (for TursoStore) |

---

## Workspace-Aware Memory

Decisions are tagged with a `workspace_id`. This enables:

- **Team isolation** — each team or project gets its own namespace
- **Multi-agent separation** — different agents write to different workspaces
- **Cross-workspace search** — query across all workspaces or filter to one

The workspace is set via the `MEMORA_WORKSPACE` environment variable or the `?workspace=` query parameter on API endpoints.

---

## API Endpoints

The Flask server (`python -m memora.app`) exposes:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/backend` | Current backend mode, workspace, storage type |
| `GET` | `/api/decisions` | List decisions (paginated) |
| `POST` | `/api/decisions` | Create a decision |
| `GET` | `/api/decisions/search?q=` | Full-text search (paginated) |
| `GET` | `/api/decisions/:id` | Get a single decision |
| `DELETE` | `/api/decisions/:id` | Delete a decision |
| `GET` | `/api/decisions/:id/links` | Get linked decisions |
| `POST` | `/api/decisions/link` | Link two decisions |
| `POST` | `/api/decisions/extract` | AI-extract decisions from text |
| `GET` | `/api/stats` | Aggregate statistics |
| `POST` | `/api/why` | AI-powered reasoning query |
| `GET` | `/api/timeline` | Decisions grouped by date |

List and search endpoints return paginated envelopes:

```json
{
  "results": [...],
  "limit": 25,
  "offset": 0,
  "count": 25
}
```

### API safeguards

- **Pagination**: max 100 results per page, default 25
- **Search query limit**: max 200 characters
- **Request body limit**: max 1 MB
- **Rate limiting**: 120 requests/minute per IP
- **Auth**: Bearer token auth when `MEMORA_API_KEY` is configured

---

## Decision Schema

Each decision record contains:

```json
{
  "id": "uuid",
  "summary": "Use PostgreSQL for metadata store",
  "reasoning": "Need JSONB support for flexible schema evolution",
  "alternatives": ["SQLite", "DynamoDB"],
  "tags": ["database", "infrastructure"],
  "type": "DECISION",
  "context": "architecture review session",
  "project": "my-agent",
  "agent": "BuilderAgent",
  "source": "manual",
  "confidence": 1.0,
  "workspace_id": "local",
  "created_at": "2025-03-28T14:30:00Z"
}
```

### Decision types

| Type | Use case |
|------|----------|
| `DECISION` | A choice that was made |
| `REJECTED` | An option that was explicitly ruled out |
| `NEXT` | A planned future action |
| `BUG_FIXED` | A bug and how it was resolved |
| `CONTEXT` | Background information relevant to decisions |
| `ASSUMPTION` | Something assumed to be true |
| `TRADEOFF` | A conscious tradeoff between competing concerns |
| `CONSTRAINT` | An external limitation that shaped a decision |
| `DEPENDENCY` | A dependency that was introduced or changed |
| `RISK` | A known risk that was accepted |

---

## Vercel Deployment

Memora includes Vercel-ready serverless functions and a cloud dashboard.

```bash
# Deploy
vercel --prod
```

The deployment includes:
- Serverless API handlers in `api/`
- Cloud dashboard at `/dashboard`
- Auto-detection of Vercel environment (switches to TursoStore)

Set these environment variables in your Vercel project:
- `TURSO_DATABASE_URL`
- `TURSO_AUTH_TOKEN`
- `MEMORA_API_KEY` (optional, enables auth)
- `GROQ_API_KEY` (optional, enables AI extraction and `/api/why`)

---

## Roadmap

- Team workspace sharing with role-based access
- Reasoning lineage graph visualization
- Compliance export support (audit trails)
- Agent decision diff viewer
- Multi-repo reasoning search

---

## Project Status

Memora is actively evolving as reasoning infrastructure for agent-native development workflows.

Current version: **0.1.0**

---

## License

MIT License
=======
# Memora
>>>>>>> 4096f2b3e677ee22e996a83380a42834f727d440
