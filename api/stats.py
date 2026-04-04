"""GET /api/stats?project= — Decision statistics."""

from http.server import BaseHTTPRequestHandler
from memora.api_utils import get_memory, check_auth, send_json, parse_query, handle_cors


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # GET is public so the dashboard can load without auth
        params = parse_query(self)
        mem = get_memory()
        stats = mem.stats(project=params.get("project", ""))
        send_json(self, 200, stats)

    def do_OPTIONS(self):
        handle_cors(self)
