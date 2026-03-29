"""
GET  /api/memories?project=&workspace=&type=&limit=50
POST /api/memories  {summary, reasoning, ...}
"""

from http.server import BaseHTTPRequestHandler
from api._utils import get_memory, check_auth, send_json, read_body, parse_query, handle_cors, parse_limit, parse_offset, paginated


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if not check_auth(self):
            return
        params = parse_query(self)
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

    def do_OPTIONS(self):
        handle_cors(self)
