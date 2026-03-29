"""
High-level memory interface that ties together storage, extraction, and retrieval.
This is the main API that other components (MCP server, CLI, hooks) consume.
"""

from typing import Optional

from memora.memory_backend import get_store
from memora.extractor import DecisionExtractor


class MemoraMemory:
    def __init__(
        self,
        db_path: Optional[str] = None,
        api_key: Optional[str] = None,
        extractor_model: str = "llama-3.3-70b-versatile",
    ):
        self.store = get_store(db_path=db_path)
        self._extractor: Optional[DecisionExtractor] = None
        self._api_key = api_key
        self._extractor_model = extractor_model

    @property
    def extractor(self) -> DecisionExtractor:
        if self._extractor is None:
            self._extractor = DecisionExtractor(api_key=self._api_key, model=self._extractor_model)
        return self._extractor

    def record(
        self,
        summary: str,
        reasoning: str,
        alternatives: Optional[list[str]] = None,
        tags: Optional[list[str]] = None,
        context: str = "",
        project: str = "",
        agent: str = "",
        source: str = "manual",
        confidence: float = 1.0,
        type: str = "DECISION",
    ) -> dict:
        return self.store.save(
            summary=summary,
            reasoning=reasoning,
            alternatives=alternatives,
            tags=tags,
            context=context,
            project=project,
            agent=agent,
            source=source,
            confidence=confidence,
            type=type,
        )

    def recall(self, query: str, limit: int = 10) -> list[dict]:
        return self.store.search(query, limit=limit)

    def recall_by_project(self, project: str, limit: int = 50) -> list[dict]:
        return self.store.list_decisions(project=project, limit=limit)

    def recall_by_tag(self, tag: str, limit: int = 50) -> list[dict]:
        return self.store.list_decisions(tag=tag, limit=limit)

    def recall_by_type(self, type: str, limit: int = 50) -> list[dict]:
        return self.store.list_decisions(type=type, limit=limit)

    def get_decision(self, decision_id: str) -> Optional[dict]:
        return self.store.get(decision_id)

    def delete_decision(self, decision_id: str) -> bool:
        return self.store.delete(decision_id)

    def link_decisions(self, from_id: str, to_id: str, relation: str = "related") -> dict:
        return self.store.link(from_id, to_id, relation)

    def get_related(self, decision_id: str) -> list[dict]:
        links = self.store.get_links(decision_id)
        related = []
        for link in links:
            other_id = link["to_id"] if link["from_id"] == decision_id else link["from_id"]
            decision = self.store.get(other_id)
            if decision:
                decision["_relation"] = link["relation"]
                related.append(decision)
        return related

    def extract_and_store(
        self,
        text: str,
        context: str = "",
        project: str = "",
        agent: str = "",
        source: str = "extracted",
    ) -> list[dict]:
        decisions = self.extractor.extract(text, context=context, project=project)
        stored = []
        for d in decisions:
            result = self.store.save(
                summary=d["summary"],
                reasoning=d["reasoning"],
                alternatives=d["alternatives"],
                tags=d["tags"],
                context=context,
                project=project,
                agent=agent,
                source=source,
                confidence=d["confidence"],
                type=d.get("type", "DECISION"),
            )
            stored.append(result)
        return stored

    def extract_from_diff_and_store(
        self,
        diff: str,
        commit_message: str = "",
        project: str = "",
        agent: str = "",
    ) -> list[dict]:
        decisions = self.extractor.extract_from_diff(diff, commit_message=commit_message, project=project)
        stored = []
        for d in decisions:
            result = self.store.save(
                summary=d["summary"],
                reasoning=d["reasoning"],
                alternatives=d["alternatives"],
                tags=d["tags"],
                context=f"commit: {commit_message}" if commit_message else "git commit",
                project=project,
                agent=agent,
                source="git-hook",
                confidence=d["confidence"],
                type=d.get("type", "DECISION"),
            )
            stored.append(result)
        return stored

    def stats(self, project: str = "") -> dict:
        return self.store.stats(project=project)

    def list_all(self, project: str = "", agent: str = "", tag: str = "", type: str = "", limit: int = 50, offset: int = 0, workspace: str = "") -> list[dict]:
        return self.store.list_decisions(project=project, agent=agent, tag=tag, type=type, limit=limit, offset=offset, workspace=workspace)

    def close(self):
        self.store.close()
