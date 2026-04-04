"""
GET    /api/decisions?limit=200      — List decisions
POST   /api/decisions                — Create a decision
DELETE /api/decisions?id=xxx         — Delete a decision
GET    /api/decisions?search=q       — Search decisions
"""

from http.server import BaseHTTPRequestHandler
from memora.api_utils import (
    get_memory, check_auth, send_json, read_body, parse_query, handle_cors,
    parse_limit, parse_offset, paginated, MAX_QUERY_LENGTH, MAX_SEARCH_RESULTS,
)


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # GET is public so the dashboard can load without auth
        params = parse_query(self)

        # Search mode: /api/decisions?search=query
        search_q = params.get("search", "") or params.get("q", "")
        if search_q:
            if len(search_q) > MAX_QUERY_LENGTH:
                send_json(self, 400, {"error": f"Query too long (max {MAX_QUERY_LENGTH} chars)"})
                return
            limit = min(parse_limit(params.get("limit"), default=20), MAX_SEARCH_RESULTS)
            mem = get_memory()
            results = mem.recall(search_q, limit=limit)
            send_json(self, 200, paginated(results, limit, 0))
            return

        # List mode
        limit = parse_limit(params.get("limit"))
        offset = parse_offset(params.get("offset"))
        mem = get_memory()
        decisions = mem.list_all(
            project=params.get("project", ""),
            agent=params.get("agent", ""),
            tag=params.get("tag", ""),
            type=params.get("type", ""),
            workspace=params.get("workspace", ""),
            limit=limit,
            offset=offset,
        )
        send_json(self, 200, paginated(decisions, limit, offset))

    def do_POST(self):
        if not check_auth(self):
            return
        data = read_body(self)
        if data is None:
            return
        if not data.get("summary") or not data.get("reasoning"):
            send_json(self, 400, {"error": "summary and reasoning are required"})
            return
        mem = get_memory()
        result = mem.record(
            summary=data["summary"],
            reasoning=data["reasoning"],
            alternatives=data.get("alternatives"),
            tags=data.get("tags"),
            context=data.get("context", ""),
            project=data.get("project", ""),
            agent=data.get("agent", ""),
            source=data.get("source", "api"),
            confidence=float(data.get("confidence", 1.0)),
            type=data.get("type", "DECISION"),
        )
        send_json(self, 201, result)

    def do_DELETE(self):
        if not check_auth(self):
            return
        params = parse_query(self)
        decision_id = params.get("id", "")
        if not decision_id:
            send_json(self, 400, {"error": "id parameter is required"})
            return
        mem = get_memory()
        deleted = mem.store.delete(decision_id)
        if deleted:
            send_json(self, 200, {"deleted": True, "id": decision_id})
        else:
            send_json(self, 404, {"error": "Decision not found"})

    def do_OPTIONS(self):
        handle_cors(self)
