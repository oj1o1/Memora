"""GET /api/sessions?project=&workspace=&limit=100 — Timeline grouped by date."""

from http.server import BaseHTTPRequestHandler
from api._utils import get_memory, check_auth, send_json, parse_query, handle_cors, parse_limit


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if not check_auth(self):
            return
        params = parse_query(self)
        limit = parse_limit(params.get("limit"))
        mem = get_memory()
        decisions = mem.list_all(
            project=params.get("project", ""),
            workspace=params.get("workspace", ""),
            limit=limit,
        )

        # Group by date as sessions
        sessions = {}
        for d in decisions:
            date = (d.get("created_at") or "")[:10]
            if date not in sessions:
                sessions[date] = []
            sessions[date].append(d)

        timeline = []
        for date in sorted(sessions.keys(), reverse=True):
            entries = sessions[date]
            has_change = any(d.get("type") in ("REJECTED", "BUG_FIXED") for d in entries)
            timeline.append({
                "date": date,
                "decisions": entries,
                "has_change": has_change,
                "count": len(entries),
            })
        send_json(self, 200, timeline)

    def do_OPTIONS(self):
        handle_cors(self)
