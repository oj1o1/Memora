"""GET /api/search?q=...&limit=20 — Full-text search decisions."""

from http.server import BaseHTTPRequestHandler
from api._utils import get_memory, check_auth, send_json, parse_query, handle_cors, parse_limit, paginated, MAX_QUERY_LENGTH, MAX_SEARCH_RESULTS


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if not check_auth(self):
            return
        params = parse_query(self)
        query = params.get("q", "")
        if not query:
            send_json(self, 400, {"error": "query parameter 'q' is required"})
            return
        if len(query) > MAX_QUERY_LENGTH:
            send_json(self, 400, {"error": f"Query too long (max {MAX_QUERY_LENGTH} chars)"})
            return
        limit = min(parse_limit(params.get("limit"), default=20), MAX_SEARCH_RESULTS)
        mem = get_memory()
        results = mem.recall(query, limit=limit)
        send_json(self, 200, paginated(results, limit, 0))

    def do_OPTIONS(self):
        handle_cors(self)
