"""
Decision extractor — uses Claude to pull structured decisions from free-form text.
Works with conversation logs, commit messages, PR descriptions, or any prose.
"""

import json
import os
from typing import Optional

from groq import Groq

EXTRACTION_PROMPT = """You are a memory-extraction engine. Given the following text, identify 3 to 8 \
important memories. Each memory must have one of these types:

- DECISION: an architectural or implementation choice that was made
- REJECTED: an approach that was tried or considered and discarded (reason field is REQUIRED)
- NEXT: something left incomplete or planned for a future session
- BUG_FIXED: a bug that was found and resolved
- CONTEXT: important context a new developer must know

For each memory return a JSON object with:

- "type": one of DECISION, REJECTED, NEXT, BUG_FIXED, CONTEXT
- "summary": one-line description (imperative mood). Be specific — use actual numbers, file names, library names
- "reasoning": why this choice was made or why this matters (2-3 sentences max)
- "reason": (REQUIRED for REJECTED only) why the approach was rejected
- "alternatives": list of alternatives that were considered (strings, may be empty)
- "tags": list of relevant topic tags (e.g. "database", "auth", "api-design")
- "confidence": float 0-1 indicating how clearly stated the memory was

Rules:
- Extract 3 to 8 memories maximum
- Be specific — use actual numbers, file names, library names
- For REJECTED always explain WHY in the reason field
- Never store raw conversation text — extract the decision only

Return a JSON array of memory objects. If no memories are found, return an empty array.
Return ONLY the JSON array, no markdown fences or extra text."""


class DecisionExtractor:
    def __init__(self, api_key: Optional[str] = None, model: str = "llama-3.3-70b-versatile"):
        self._api_key = api_key or os.getenv("GROQ_API_KEY")
        self._client = None
        self.model = model

    @property
    def client(self):
        if self._client is None:
            if not self._api_key:
                raise RuntimeError(
                    "GROQ_API_KEY not set. AI extraction requires a Groq API key.\n"
                    "Set it via: export GROQ_API_KEY=gsk_...\n"
                    "Record/recall works without it — only extract needs it."
                )
            self._client = Groq(api_key=self._api_key)
        return self._client

    @property
    def available(self) -> bool:
        """Check if AI extraction is available (API key configured)."""
        return bool(self._api_key)

    def extract(self, text: str, context: str = "", project: str = "") -> list[dict]:
        if not text.strip():
            return []

        if not self.available:
            return self._fallback_extract(text)

        user_content = text
        if context:
            user_content = f"Context: {context}\n\n{user_content}"
        if project:
            user_content = f"Project: {project}\n\n{user_content}"

        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=4096,
            messages=[
                {"role": "system", "content": EXTRACTION_PROMPT},
                {"role": "user", "content": user_content},
            ],
        )

        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        try:
            decisions = json.loads(raw)
        except json.JSONDecodeError:
            return []

        if not isinstance(decisions, list):
            return []

        cleaned = []
        for d in decisions:
            if not isinstance(d, dict):
                continue
            dtype = str(d.get("type", "DECISION")).upper()
            if dtype not in {"DECISION", "REJECTED", "NEXT", "BUG_FIXED", "CONTEXT"}:
                dtype = "DECISION"
            reasoning = str(d.get("reasoning", ""))
            # For REJECTED type, incorporate the reason into reasoning if present
            reason = str(d.get("reason", ""))
            if dtype == "REJECTED" and reason:
                reasoning = f"Rejected because: {reason}" if not reasoning else f"{reasoning} Rejected because: {reason}"
            cleaned.append({
                "type": dtype,
                "summary": str(d.get("summary", "")),
                "reasoning": reasoning,
                "alternatives": [str(a) for a in d.get("alternatives", []) if a],
                "tags": [str(t) for t in d.get("tags", []) if t],
                "confidence": float(d.get("confidence", 0.8)),
            })
        return cleaned

    def extract_from_diff(self, diff: str, commit_message: str = "", project: str = "") -> list[dict]:
        text = ""
        if commit_message:
            text += f"Commit message:\n{commit_message}\n\n"
        text += f"Code diff:\n{diff}"
        return self.extract(text, context="git commit", project=project)

    def extract_from_conversation(self, messages: list[dict], project: str = "") -> list[dict]:
        lines = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            lines.append(f"[{role}]: {content}")
        text = "\n".join(lines)
        return self.extract(text, context="agent conversation", project=project)

    @staticmethod
    def _fallback_extract(text: str) -> list[dict]:
        """Simple regex-based extraction when no API key is available.
        Looks for common decision patterns in text."""
        import re
        decisions = []
        patterns = [
            (r"(?:decided|chose|picked|selected|went with|using|switched to)\s+(.+?)(?:\.|$)", "DECISION"),
            (r"(?:rejected|ruled out|dropped|abandoned|ditched)\s+(.+?)(?:\.|$)", "REJECTED"),
            (r"(?:TODO|FIXME|next time|will need to|should later)\s*:?\s*(.+?)(?:\.|$)", "NEXT"),
            (r"(?:fixed|resolved|patched|bug was)\s+(.+?)(?:\.|$)", "BUG_FIXED"),
        ]
        for pattern, dtype in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE):
                summary = match.group(1).strip()[:120]
                if len(summary) > 10:
                    decisions.append({
                        "type": dtype,
                        "summary": summary,
                        "reasoning": "Auto-extracted (offline — no API key)",
                        "alternatives": [],
                        "tags": [],
                        "confidence": 0.5,
                    })
        return decisions[:8]
