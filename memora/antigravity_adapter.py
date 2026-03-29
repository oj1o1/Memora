"""
Antigravity adapter for Memora.

Integrates Memora as a memory backend for Antigravity-based agent frameworks.
Provides both a class-based adapter and simple function API for one-liner usage.

Usage (simple — works directly in any Antigravity session):
    from memora.antigravity_adapter import record_decision, ask_memory

    record_decision(
        agent="RefundAgent",
        decision="Switched retrieval strategy",
        reason="semantic similarity failure",
        alternatives=["BM25 fallback"]
    )

    results = ask_memory("retrieval strategy")

Usage (class-based — for more control):
    from memora.antigravity_adapter import MemoraAdapter

    adapter = MemoraAdapter(project="my-agent")
    adapter.on_decision("Use PostgreSQL", reasoning="Need JSONB support")
    results = adapter.query("database choice")
"""

import json
import os
from typing import Any, Optional

from pathlib import Path
from dotenv import load_dotenv

from memora.memory import MemoraMemory

load_dotenv(Path(__file__).parent / ".env")

# Auto-load saved cloud config
_config_path = Path.home() / ".memora" / "config.json"
if _config_path.exists():
    try:
        _cfg = json.loads(_config_path.read_text(encoding="utf-8"))
        for _k in ("MEMORA_API_URL", "MEMORA_API_KEY"):
            if _k in _cfg and not os.getenv(_k):
                os.environ[_k] = _cfg[_k]
    except Exception:
        pass


class MemoraAdapter:
    """Adapter that exposes Memora as a tool/memory layer for agent frameworks."""

    def __init__(
        self,
        project: str = "",
        agent: str = "",
        db_path: Optional[str] = None,
        api_key: Optional[str] = None,
        auto_extract: bool = True,
    ):
        self.project = project
        self.agent = agent
        self.auto_extract = auto_extract
        self._memory = MemoraMemory(
            db_path=db_path or os.getenv("MEMORA_DB_PATH"),
            api_key=api_key or os.getenv("GROQ_API_KEY"),
        )

    def on_decision(
        self,
        summary: str,
        reasoning: str = "",
        alternatives: Optional[list[str]] = None,
        tags: Optional[list[str]] = None,
        context: str = "",
        confidence: float = 1.0,
        type: str = "DECISION",
    ) -> dict:
        """Record a decision made by an agent.

        Args:
            type: Memory type — DECISION, REJECTED, NEXT, BUG_FIXED, or CONTEXT
        """
        return self._memory.record(
            summary=summary,
            reasoning=reasoning,
            alternatives=alternatives,
            tags=tags,
            context=context,
            project=self.project,
            agent=self.agent,
            source="antigravity",
            confidence=confidence,
            type=type,
        )

    def on_message(self, role: str, content: str) -> list[dict]:
        """Process an agent message and optionally extract decisions from it.
        Returns list of extracted decisions (empty if auto_extract is off)."""
        if not self.auto_extract:
            return []
        return self._memory.extract_and_store(
            text=f"[{role}]: {content}",
            context="agent-message",
            project=self.project,
            agent=self.agent,
            source="antigravity-auto",
        )

    def on_conversation_end(self, messages: list[dict]) -> list[dict]:
        """Process a complete conversation and extract decisions."""
        lines = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            lines.append(f"[{role}]: {content}")
        text = "\n".join(lines)
        return self._memory.extract_and_store(
            text=text,
            context="agent-conversation",
            project=self.project,
            agent=self.agent,
            source="antigravity-conversation",
        )

    def query(self, query: str, limit: int = 10) -> list[dict]:
        """Search for past decisions relevant to the query."""
        return self._memory.recall(query, limit=limit)

    def recall_by_type(self, type: str, limit: int = 10) -> list[dict]:
        """Search for past decisions by memory type."""
        return self._memory.recall_by_type(type, limit=limit)

    def get_context(self, query: str, limit: int = 5) -> str:
        """Get a formatted string of relevant past decisions for injection into agent prompts."""
        decisions = self._memory.recall(query, limit=limit)
        if not decisions:
            return "No relevant past decisions found."

        parts = ["Relevant past decisions:"]
        for d in decisions:
            dtype = d.get("type", "DECISION")
            alts = ", ".join(d.get("alternatives", []))
            entry = f"- [{dtype}] {d['summary']}: {d['reasoning']}"
            if alts:
                entry += f" (alternatives rejected: {alts})"
            parts.append(entry)
        return "\n".join(parts)

    def get_tool_definitions(self) -> list[dict]:
        """Return tool definitions that can be registered with an agent framework."""
        return [
            {
                "name": "memora_record_decision",
                "description": "Record a development decision with its reasoning for future reference.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "summary": {"type": "string", "description": "One-line summary of the decision"},
                        "reasoning": {"type": "string", "description": "Why this choice was made"},
                        "type": {
                            "type": "string",
                            "enum": ["DECISION", "REJECTED", "NEXT", "BUG_FIXED", "CONTEXT"],
                            "description": "Memory type",
                            "default": "DECISION",
                        },
                        "alternatives": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Alternatives that were considered",
                        },
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Topic tags",
                        },
                    },
                    "required": ["summary", "reasoning"],
                },
            },
            {
                "name": "memora_recall_decisions",
                "description": "Search past decisions by keyword or topic.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "limit": {"type": "integer", "description": "Max results", "default": 10},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "memora_recall_by_type",
                "description": "List decisions filtered by memory type (DECISION, REJECTED, NEXT, BUG_FIXED, CONTEXT).",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": ["DECISION", "REJECTED", "NEXT", "BUG_FIXED", "CONTEXT"],
                            "description": "Memory type to filter by",
                        },
                        "limit": {"type": "integer", "description": "Max results", "default": 10},
                    },
                    "required": ["type"],
                },
            },
        ]

    def handle_tool_call(self, tool_name: str, tool_input: dict) -> Any:
        """Handle a tool call from an agent framework."""
        if tool_name == "memora_record_decision":
            return self.on_decision(
                summary=tool_input["summary"],
                reasoning=tool_input.get("reasoning", ""),
                alternatives=tool_input.get("alternatives"),
                tags=tool_input.get("tags"),
                type=tool_input.get("type", "DECISION"),
            )
        elif tool_name == "memora_recall_decisions":
            return self.query(
                query=tool_input["query"],
                limit=tool_input.get("limit", 10),
            )
        elif tool_name == "memora_recall_by_type":
            return self.recall_by_type(
                type=tool_input["type"],
                limit=tool_input.get("limit", 10),
            )
        else:
            return {"error": f"Unknown tool: {tool_name}"}

    def stats(self) -> dict:
        """Get statistics about stored decisions."""
        return self._memory.stats(project=self.project)

    def close(self):
        """Clean up resources."""
        self._memory.close()


# ---------------------------------------------------------------------------
# Module-level convenience functions (singleton adapter)
# ---------------------------------------------------------------------------
# These let any Antigravity agent call Memora with zero setup:
#   from memora.antigravity_adapter import record_decision, ask_memory

_default_adapter: Optional[MemoraAdapter] = None


def _get_default() -> MemoraAdapter:
    """Lazy-init a shared adapter instance."""
    global _default_adapter
    if _default_adapter is None:
        _default_adapter = MemoraAdapter(
            project=os.getenv("MEMORA_PROJECT", ""),
            agent=os.getenv("MEMORA_AGENT", ""),
        )
    return _default_adapter


def record_decision(
    decision: str,
    reason: str = "",
    agent: str = "",
    alternatives: Optional[list[str]] = None,
    tags: Optional[list[str]] = None,
    type: str = "DECISION",
) -> dict:
    """Record a decision from an Antigravity agent session.

    Args:
        decision: What was decided (one-line summary)
        reason: Why this choice was made
        agent: Which agent made the decision (e.g. "RefundAgent")
        alternatives: Other options that were considered
        tags: Topic tags
        type: DECISION, REJECTED, NEXT, BUG_FIXED, or CONTEXT
    """
    adapter = _get_default()
    if agent:
        adapter.agent = agent
    return adapter.on_decision(
        summary=decision,
        reasoning=reason,
        alternatives=alternatives,
        tags=tags,
        type=type,
    )


def ask_memory(query: str, limit: int = 10) -> list[dict]:
    """Search past decisions by keyword or topic.

    Args:
        query: What to search for
        limit: Max results to return
    """
    return _get_default().query(query, limit=limit)


def get_context(query: str, limit: int = 5) -> str:
    """Get formatted past decisions for injection into an agent prompt."""
    return _get_default().get_context(query, limit=limit)


def session_end(messages: list[dict]) -> list[dict]:
    """Extract decisions from a completed conversation."""
    return _get_default().on_conversation_end(messages)


def memory_stats() -> dict:
    """Get statistics about stored decisions."""
    return _get_default().stats()
