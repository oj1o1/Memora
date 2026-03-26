# Memora

**Decision memory layer for AI agent builders.** Captures WHY decisions were made during development, not production traces. Think Git for agent reasoning.

## What it does

Every time an AI agent (or human) makes a technical decision — choosing a database, picking an API pattern, selecting a framework — Memora captures the decision, the reasoning, and what alternatives were rejected. This creates a searchable history of architectural knowledge that survives across sessions, agents, and team members.

## Quick Start

```bash
pip install -r requirements.txt
cp .env.example .env  # add your ANTHROPIC_API_KEY
```

### CLI

```bash
# Record a decision manually
python -m memora.cli record "Use PostgreSQL for the main database" \
  -r "Need JSONB support for flexible schemas and strong ecosystem" \
  -a "MongoDB" -a "SQLite" \
  -t database -t infrastructure \
  -p my-project

# Search past decisions
python -m memora.cli search "database"

# List all decisions
python -m memora.cli list --project my-project

# Extract decisions from text using AI
cat meeting-notes.txt | python -m memora.cli extract -p my-project

# View stats
python -m memora.cli stats
```

### MCP Server

Add to your MCP client config:

```json
{
  "mcpServers": {
    "memora": {
      "command": "python",
      "args": ["-m", "memora.server"],
      "env": {
        "ANTHROPIC_API_KEY": "sk-ant-..."
      }
    }
  }
}
```

Available tools: `record_decision`, `recall_decisions`, `get_decision`, `list_decisions`, `extract_decisions`, `link_decisions`, `get_related_decisions`, `delete_decision`, `decision_stats`.

### Web Dashboard

```bash
python -m memora.cli web
# Opens at http://127.0.0.1:8377
```

### REST API

```bash
# Create a decision
curl -X POST http://localhost:8377/api/decisions \
  -H "Content-Type: application/json" \
  -d '{"summary": "Use REST over GraphQL", "reasoning": "Simpler for our use case"}'

# Search
curl http://localhost:8377/api/decisions/search?q=database

# List all
curl http://localhost:8377/api/decisions

# Stats
curl http://localhost:8377/api/stats
```

## Integrations

### Git Hook

Automatically extract decisions from commits:

```bash
python -m memora.git_hook install
```

### Cursor IDE

Install Cursor rules that prompt the agent to record decisions:

```bash
python -m memora.cursor_hook install
```

### Agent Frameworks

```python
from memora.antigravity_adapter import MemoraAdapter

adapter = MemoraAdapter(project="my-agent")

# Record decisions programmatically
adapter.on_decision(
    "Use streaming responses",
    reasoning="Reduces time-to-first-token for better UX",
    alternatives=["Batch responses", "Server-sent events"],
    tags=["api", "ux"]
)

# Query past decisions for context injection
context = adapter.get_context("response format")
# Returns formatted string ready to inject into agent prompts

# Get tool definitions for agent registration
tools = adapter.get_tool_definitions()
```

## Configuration

Environment variables (or `.env` file):

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Required for AI extraction |
| `MEMORA_DB_PATH` | `~/.memora/decisions.db` | SQLite database location |
| `MEMORA_HOST` | `127.0.0.1` | Web server host |
| `MEMORA_PORT` | `8377` | Web server port |

## Architecture

```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   CLI (cli)  │  │  MCP Server  │  │  Flask API   │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                 │
       └────────┬────────┴────────┬────────┘
                │                 │
         ┌──────┴──────┐  ┌──────┴──────┐
         │   Memory    │  │  Extractor  │
         │  (memory)   │  │ (extractor) │
         └──────┬──────┘  └─────────────┘
                │
         ┌──────┴──────┐
         │    Store    │
         │   (store)   │
         │  SQLite+FTS │
         └─────────────┘
```

All consumer layers (CLI, MCP, Flask, hooks, adapters) go through the `MemoraMemory` class, which coordinates the `DecisionStore` (persistence) and `DecisionExtractor` (AI extraction).
