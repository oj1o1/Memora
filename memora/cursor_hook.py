"""
Cursor IDE hook for Memora.

Integrates with Cursor's agent mode by providing a rules file and a
post-response hook that extracts decisions from agent conversations.

Usage:
    python -m memora.cursor_hook install [--project myproject]
    python -m memora.cursor_hook extract <logfile> [--project myproject]
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from memora.memory import MemoraMemory

load_dotenv()

CURSOR_RULES_TEMPLATE = """# Memora Decision Tracking

When you make a technical decision, architectural choice, reject an approach, fix a bug,
or note important context, append a markdown block at the end of your response:

```memora-decision
type: <DECISION | REJECTED | NEXT | BUG_FIXED | CONTEXT>
summary: <one-line summary — be specific with file names, numbers, library names>
reasoning: <why this choice was made>
reason: <(REJECTED only) why the approach was rejected>
alternatives: <comma-separated list of alternatives considered>
tags: <comma-separated topic tags>
```

Types:
- DECISION: an architectural or implementation choice that was made
- REJECTED: an approach that was tried or considered and discarded (always fill reason)
- NEXT: something left incomplete or planned for next session
- BUG_FIXED: a bug that was found and resolved
- CONTEXT: important context a new developer must know

This helps maintain a searchable history of WHY things were built the way they are.
"""


def install_cursor_rules(project_dir: str = ".", project_name: str = ""):
    project_path = Path(project_dir).resolve()
    cursor_dir = project_path / ".cursor"
    cursor_dir.mkdir(exist_ok=True)

    rules_file = cursor_dir / "rules" / "memora.mdc"
    rules_file.parent.mkdir(exist_ok=True)

    frontmatter = "---\ndescription: Memora decision tracking\nglobs: \"**/*\"\nalwaysApply: true\n---\n\n"
    rules_file.write_text(frontmatter + CURSOR_RULES_TEMPLATE, encoding="utf-8")

    print(f"Installed Cursor rules at {rules_file}")
    return str(rules_file)


def extract_decisions_from_log(log_path: str, project: str = "", agent: str = "cursor") -> list[dict]:
    path = Path(log_path)
    if not path.exists():
        print(f"Log file not found: {log_path}", file=sys.stderr)
        return []

    text = path.read_text(encoding="utf-8")

    manual_decisions = _parse_memora_blocks(text)

    mem = MemoraMemory(
        db_path=os.getenv("MEMORA_DB_PATH"),
        api_key=os.getenv("GROQ_API_KEY"),
    )

    stored = []
    for d in manual_decisions:
        result = mem.record(
            summary=d["summary"],
            reasoning=d["reasoning"],
            alternatives=d.get("alternatives", []),
            tags=d.get("tags", []),
            context="cursor-agent",
            project=project,
            agent=agent,
            source="cursor-hook",
            confidence=0.9,
            type=d.get("type", "DECISION"),
        )
        stored.append(result)

    ai_decisions = mem.extract_and_store(
        text=text, context="cursor-agent-log", project=project, agent=agent, source="cursor-extract"
    )
    stored.extend(ai_decisions)

    return stored


def _parse_memora_blocks(text: str) -> list[dict]:
    decisions = []
    marker = "```memora-decision"
    parts = text.split(marker)
    for part in parts[1:]:
        end = part.find("```")
        if end == -1:
            block = part
        else:
            block = part[:end]

        d: dict = {"type": "DECISION", "summary": "", "reasoning": "", "alternatives": [], "tags": []}
        for line in block.strip().splitlines():
            line = line.strip()
            if line.startswith("type:"):
                dtype = line.split(":", 1)[1].strip().upper()
                if dtype in {"DECISION", "REJECTED", "NEXT", "BUG_FIXED", "CONTEXT"}:
                    d["type"] = dtype
            elif line.startswith("summary:"):
                d["summary"] = line.split(":", 1)[1].strip()
            elif line.startswith("reasoning:"):
                d["reasoning"] = line.split(":", 1)[1].strip()
            elif line.startswith("reason:"):
                reason = line.split(":", 1)[1].strip()
                if reason:
                    d["reasoning"] = f"{d['reasoning']} Rejected because: {reason}" if d["reasoning"] else f"Rejected because: {reason}"
            elif line.startswith("alternatives:"):
                raw = line.split(":", 1)[1].strip()
                d["alternatives"] = [a.strip() for a in raw.split(",") if a.strip()]
            elif line.startswith("tags:"):
                raw = line.split(":", 1)[1].strip()
                d["tags"] = [t.strip() for t in raw.split(",") if t.strip()]

        if d["summary"]:
            decisions.append(d)

    return decisions


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python -m memora.cursor_hook install [--project NAME]")
        print("  python -m memora.cursor_hook extract <logfile> [--project NAME]")
        sys.exit(1)

    command = sys.argv[1]

    if command == "install":
        project = ""
        if "--project" in sys.argv:
            idx = sys.argv.index("--project")
            if idx + 1 < len(sys.argv):
                project = sys.argv[idx + 1]
        install_cursor_rules(project_name=project)

    elif command == "extract":
        if len(sys.argv) < 3:
            print("Usage: python -m memora.cursor_hook extract <logfile> [--project NAME]")
            sys.exit(1)
        logfile = sys.argv[2]
        project = ""
        if "--project" in sys.argv:
            idx = sys.argv.index("--project")
            if idx + 1 < len(sys.argv):
                project = sys.argv[idx + 1]
        results = extract_decisions_from_log(logfile, project=project)
        print(f"Extracted {len(results)} decisions")
        print(json.dumps(results, indent=2))

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
