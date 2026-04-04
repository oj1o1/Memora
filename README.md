# Memora

**Git tracks what changed. Memora tracks why.**

Decision memory infrastructure for AI agent builders. Records the reasoning behind every engineering decision — so context is never lost when teams scale.

[Live Demo](https://memora-one-olive.vercel.app) | [Dashboard](https://memora-one-olive.vercel.app/dashboard)

---

## The Problem

Most agent bugs aren't in the code. They come from forgotten decisions.

A prompt was reworded. A tool was swapped. A threshold was raised. The agent broke — and no one remembers why the original choice was made.

These decisions live in chat logs, PR descriptions, and engineers' heads. When something breaks weeks later, the team reverse-engineers intent from code that was never designed to explain itself.

**Memora fixes this.** It captures decisions as structured, searchable memory — the summary, the reasoning, the alternatives considered — so any engineer can ask *"why was this built this way?"* and get an instant answer.

---

## Quick Start

```bash
# Install
pip install git+https://github.com/oj1o1/Memora.git#egg=memora[all]

# Record a decision
memora record "Use BM25 over vector search" \
  --reasoning "Better recall on short queries, deterministic results" \
  --type DECISION --tags search,retrieval

# Search decisions
memora search "search strategy"

# Launch dashboard
python -m memora.app
# Open http://localhost:8377
```

---

## Use with Claude Code / Cursor / Any MCP Client

Add to `.mcp.json` in your project:

```json
{
  "mcpServers": {
    "memora": {
      "command": "python",
      "args": ["-m", "memora.server"],
      "env": {
        "GROQ_API_KEY": "your-groq-key"
      }
    }
  }
}
```

Then just talk naturally:

> *"Record a decision: we chose PostgreSQL over MongoDB because we need ACID transactions"*

> *"Why did we choose PostgreSQL?"*

> *"What approaches were rejected for the auth system?"*

---

## How It Works

```
Engineer works with AI agent
        |
        v
    Decisions happen naturally
    ("Let's use BM25 instead of vectors")
        |
        v
    Memora captures WHY
    [DECISION] Use BM25 — better recall on short queries
    [REJECTED] Vector search — degraded below 5-word queries
    [CONSTRAINT] Client needs deterministic outputs
        |
        v
    Weeks later, new engineer asks:
    "Why don't we use vector search?"
        |
        v
    Memora answers instantly with full context
```

---

## 10 Decision Types

| Type | What it captures |
|------|-----------------|
| `DECISION` | An architectural or implementation choice |
| `REJECTED` | An approach tried and discarded — always includes why |
| `NEXT` | Something planned for the next session |
| `BUG_FIXED` | A bug that was found and resolved |
| `CONTEXT` | Important context a new developer must know |
| `ASSUMPTION` | Something assumed true that may change |
| `TRADEOFF` | A conscious trade between competing concerns |
| `CONSTRAINT` | An external limitation shaping decisions |
| `DEPENDENCY` | A critical external dependency |
| `RISK` | A known risk accepted for now |

---

## Architecture

```
                    MCP Server
                   (Claude Code,
                    Cursor, etc.)
                        |
                        v
  CLI -----> MemoraMemory <-----> Groq AI Extractor
                |                 (llama-3.3-70b)
                v
          memory_backend.py
           /          \
     LocalStore    TursoStore
     (SQLite)      (Cloud libSQL)
          \          /
           Dashboard
        (Flask / Vercel)
```

- **Local mode**: SQLite with WAL + FTS5 full-text search. Zero config.
- **Cloud mode**: Turso (edge-replicated libSQL). Same queries, persistent storage.
- **AI extraction**: Groq (llama-3.3-70b) for real-time decision extraction from conversations.
- **MCP server**: FastMCP — one server covers Claude Code, Cursor, Claude Desktop.

---

## Features

- **Reasoning Timeline** — Scroll through sessions with visual change markers
- **Change Diff View** — Side-by-side FROM/TO comparisons when decisions change
- **"Why?" Query Panel** — Natural language questions answered from decision history
- **Behavior Lineage** — Trace how reasoning evolved over time
- **10 Memory Types** — Structured extraction: DECISION, REJECTED, TRADEOFF, CONSTRAINT...
- **MCP + CLI + API** — Works with any AI coding tool
- **Cloud Sync** — Turso-backed storage syncs across local MCP and Vercel dashboard
- **Git Hooks** — Auto-extract decisions from commits
- **Agent Framework Adapter** — Built-in Antigravity support

---

## Live Demo

**Landing page**: [memora-one-olive.vercel.app](https://memora-one-olive.vercel.app)
**Dashboard**: [memora-one-olive.vercel.app/dashboard](https://memora-one-olive.vercel.app/dashboard)

The dashboard shows 24 real decisions made while building Memora itself — the project eats its own dog food.

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/decisions` | List all decisions (paginated) |
| POST | `/api/decisions` | Record a new decision |
| DELETE | `/api/decisions?id=` | Delete a decision |
| GET | `/api/decisions?search=` | Full-text search |
| POST | `/api/why` | AI-powered reasoning query |
| GET | `/api/stats` | Statistics by type/tag/source |
| GET | `/api/backend` | Current backend mode |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Storage | SQLite (WAL + FTS5) / Turso (cloud) |
| AI | Groq + Llama 3.3 70B |
| MCP | FastMCP |
| Web | Flask (local) / Vercel (cloud) |
| Frontend | Vanilla HTML/CSS/JS (zero deps) |
| Language | Python 3.9+ |

---

## Why Not Just Use Git Blame?

| | Git | Memora |
|---|-----|--------|
| **Tracks** | What changed | Why it changed |
| **Granularity** | File/line level | Decision level |
| **Reasoning** | Commit message (if you're lucky) | Full reasoning + alternatives |
| **Queryable** | `git log --grep` | Natural language: "Why did X change?" |
| **Structured** | Free text | Typed: DECISION, REJECTED, TRADEOFF... |
| **Cross-session** | Per-commit | Traces reasoning evolution over time |

---

## License

MIT
