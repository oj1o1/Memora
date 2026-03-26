"""
Memora — decision memory layer for AI agent builders.

Quick start:
    from memora import record_decision, ask_memory

    record_decision(
        decision="Use Redis for caching",
        reason="Need sub-ms latency for session lookups",
    )

    results = ask_memory("caching strategy")
"""

__version__ = "0.1.0"

# Re-export convenience functions so users can do:
#   from memora import record_decision, ask_memory
from memora.antigravity_adapter import (
    record_decision,
    ask_memory,
    get_context,
    session_end,
    memory_stats,
)

__all__ = [
    "record_decision",
    "ask_memory",
    "get_context",
    "session_end",
    "memory_stats",
]
