"""Shared utilities for Vercel serverless API handlers."""

import json
import os
import sys

# Ensure the project root is in path so `memora` package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from memora.memory import MemoraMemory
from memora.api_limits import (
    parse_limit, parse_offset, paginated,
    MAX_QUERY_LENGTH, MAX_SEARCH_RESULTS, MAX_REQUEST_BYTES,
)

_memory = None


def get_memory() -> MemoraMemory:
    global _memory
    if _memory is None:
        _memory = MemoraMemory(
            db_path=os.getenv("MEMORA_DB_PATH"),
            api_key=os.getenv("GROQ_API_KEY"),
        )
    return _memory


def check_auth(handler_self) -> bool:
    """Check Bearer token auth. Returns True if authorized, False if rejected (response already sent)."""
    server_key = os.getenv("MEMORA_API_KEY", "")
    if not server_key:
        return True
    auth = handler_self.headers.get("Authorization", "")
    if not auth.startswith("Bearer ") or auth[7:] != server_key:
        send_json(handler_self, 401, {"error": "Unauthorized"})
        return False
    return True


def send_json(handler_self, status: int, data):
    """Send a JSON response."""
    body = json.dumps(data).encode("utf-8")
    handler_self.send_response(status)
    handler_self.send_header("Content-Type", "application/json")
    handler_self.send_header("Access-Control-Allow-Origin", "*")
    handler_self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
    handler_self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
    handler_self.end_headers()
    handler_self.wfile.write(body)


def read_body(handler_self):
    """Read and parse JSON request body. Returns None if body exceeds MAX_REQUEST_BYTES."""
    length = int(handler_self.headers.get("Content-Length", 0))
    if length == 0:
        return {}
    if length > MAX_REQUEST_BYTES:
        send_json(handler_self, 413, {"error": "Request body too large", "max_bytes": MAX_REQUEST_BYTES})
        return None
    raw = handler_self.rfile.read(length)
    return json.loads(raw)


def parse_query(handler_self) -> dict:
    """Parse query string parameters from the URL."""
    from urllib.parse import urlparse, parse_qs
    parsed = urlparse(handler_self.path)
    params = parse_qs(parsed.query)
    # Flatten single values
    return {k: v[0] if len(v) == 1 else v for k, v in params.items()}


def handle_cors(handler_self):
    """Handle CORS preflight."""
    handler_self.send_response(204)
    handler_self.send_header("Access-Control-Allow-Origin", "*")
    handler_self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
    handler_self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
    handler_self.end_headers()
