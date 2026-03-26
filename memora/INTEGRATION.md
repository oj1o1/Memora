# Memora + Antigravity Integration (5 min setup)

## 1. Clone & install

```bash
git clone https://github.com/YOUR_USERNAME/Memora.git
cd Memora
pip install -r memora/requirements.txt
```

## 2. Set up `.env`

```bash
cp memora/.env.example memora/.env
```

Edit `memora/.env` and add your Groq API key:

```
GROQ_API_KEY=gsk_...
```

## 3. Use in any Antigravity agent — 2 lines

```python
from memora.antigravity_adapter import record_decision, ask_memory

# Save a decision
record_decision(
    agent="RefundAgent",
    decision="Switched to BM25 retrieval",
    reason="Semantic similarity was failing on short queries",
    alternatives=["vector search", "hybrid search"]
)

# Query past decisions
results = ask_memory("retrieval strategy")
```

## 4. Optional — inject memory into agent prompts

```python
from memora.antigravity_adapter import get_context

# Get formatted context to prepend to system prompt
context = get_context("database choice")
# Returns: "Relevant past decisions:\n- [DECISION] ..."
```

## 5. Optional — auto-extract from conversations

```python
from memora.antigravity_adapter import session_end

messages = [
    {"role": "user", "content": "Let's use Redis for caching"},
    {"role": "assistant", "content": "Agreed, Redis over Memcached because..."}
]
session_end(messages)  # AI extracts decisions automatically
```

## 6. Optional — view decisions in browser

```bash
python -m memora.app
# Open http://127.0.0.1:8377/dashboard
```

## Available functions

| Function | Purpose |
|---|---|
| `record_decision(decision, reason, agent, alternatives, tags)` | Store a decision with reasoning |
| `ask_memory(query, limit)` | Search past decisions by keyword |
| `get_context(query, limit)` | Get formatted decisions for prompt injection |
| `session_end(messages)` | Auto-extract decisions from a conversation |
| `memory_stats()` | Get decision counts and stats |

## How it works

```
Antigravity agent
      ↓
antigravity_adapter.py  (convenience functions)
      ↓
SQLite reasoning memory  (~/.memora/decisions.db)
      ↓
MCP server (optional)    (python -m memora.server)
      ↓
Claude / Cursor access
```

- **Antigravity writes** memory via `record_decision()` / `session_end()`
- **Claude / Cursor reads** memory via MCP server or REST API
- All agents on the same machine share the same SQLite database

No MCP config, no tool registration, no marketplace listing needed. Just `import` and call.
