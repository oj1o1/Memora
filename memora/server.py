"""
FastMCP server exposing Memora as tool endpoints.
Run with: python -m memora.server
"""

import os
from typing import Optional

from dotenv import load_dotenv
from fastmcp import FastMCP

from memora.memory import MemoraMemory

load_dotenv()

mcp = FastMCP(
    "Memora",
    description="Decision memory layer — captures WHY decisions were made during development.",
)

_memory: Optional[MemoraMemory] = None


def get_memory() -> MemoraMemory:
    global _memory
    if _memory is None:
        _memory = MemoraMemory(
            db_path=os.getenv("MEMORA_DB_PATH"),
            api_key=os.getenv("GROQ_API_KEY"),
        )
    return _memory


@mcp.tool()
def record_decision(
    summary: str,
    reasoning: str,
    type: str = "DECISION",
    alternatives: Optional[list[str]] = None,
    tags: Optional[list[str]] = None,
    context: str = "",
    project: str = "",
    agent: str = "",
    confidence: float = 1.0,
) -> dict:
    """Record a development decision with its reasoning.

    Args:
        summary: One-line description of what was decided
        reasoning: Why this choice was made
        type: Memory type — DECISION, REJECTED, NEXT, BUG_FIXED, or CONTEXT
        alternatives: Other options that were considered
        tags: Topic tags (e.g. "database", "auth")
        context: Where this decision was made
        project: Project identifier
        agent: Agent or person who made the decision
        confidence: How clearly stated the decision is (0-1)
    """
    return get_memory().record(
        summary=summary,
        reasoning=reasoning,
        alternatives=alternatives,
        tags=tags,
        context=context,
        project=project,
        agent=agent,
        source="mcp",
        confidence=confidence,
        type=type,
    )


@mcp.tool()
def recall_decisions(query: str, limit: int = 10) -> list[dict]:
    """Search past decisions by keyword or topic.

    Args:
        query: Search query — matches against summaries, reasoning, tags
        limit: Maximum number of results
    """
    return get_memory().recall(query, limit=limit)


@mcp.tool()
def get_decision(decision_id: str) -> dict:
    """Get a specific decision by its ID.

    Args:
        decision_id: The decision identifier
    """
    result = get_memory().get_decision(decision_id)
    if result is None:
        return {"error": "Decision not found"}
    return result


@mcp.tool()
def list_decisions(
    project: str = "",
    agent: str = "",
    tag: str = "",
    type: str = "",
    limit: int = 50,
) -> list[dict]:
    """List decisions with optional filters.

    Args:
        project: Filter by project
        agent: Filter by agent
        tag: Filter by tag
        type: Filter by type (DECISION, REJECTED, NEXT, BUG_FIXED, CONTEXT)
        limit: Maximum results
    """
    return get_memory().list_all(project=project, agent=agent, tag=tag, type=type, limit=limit)


@mcp.tool()
def extract_decisions(
    text: str,
    context: str = "",
    project: str = "",
    agent: str = "",
) -> list[dict]:
    """Extract decisions from free-form text using AI and store them.

    Args:
        text: Text containing decisions (conversation log, meeting notes, etc.)
        context: Where the text came from
        project: Project identifier
        agent: Agent that produced the text
    """
    return get_memory().extract_and_store(
        text=text, context=context, project=project, agent=agent, source="mcp-extract"
    )


@mcp.tool()
def link_decisions(from_id: str, to_id: str, relation: str = "related") -> dict:
    """Link two related decisions together.

    Args:
        from_id: Source decision ID
        to_id: Target decision ID
        relation: Type of relationship (e.g. "supersedes", "related", "caused_by")
    """
    return get_memory().link_decisions(from_id, to_id, relation)


@mcp.tool()
def get_related_decisions(decision_id: str) -> list[dict]:
    """Get all decisions linked to a given decision.

    Args:
        decision_id: The decision to find relations for
    """
    return get_memory().get_related(decision_id)


@mcp.tool()
def delete_decision(decision_id: str) -> dict:
    """Delete a decision by ID.

    Args:
        decision_id: The decision to delete
    """
    ok = get_memory().delete_decision(decision_id)
    return {"deleted": ok, "id": decision_id}


@mcp.tool()
def decision_stats(project: str = "") -> dict:
    """Get statistics about stored decisions.

    Args:
        project: Optionally scope stats to a project
    """
    return get_memory().stats(project=project)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
