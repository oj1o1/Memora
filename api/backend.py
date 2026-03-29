"""GET /api/backend — Return current backend mode, workspace, and storage type."""

from http.server import BaseHTTPRequestHandler
from memora.api_utils import send_json, handle_cors

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        from memora.memory_backend import get_backend_mode
        from memora.store import VALID_TYPES
        mode = get_backend_mode()
        storage_map = {"LOCAL": "sqlite", "REMOTE": "api", "TURSO": "cloud"}
        send_json(self, 200, {
            "mode": mode,
            "workspace": os.getenv("MEMORA_WORKSPACE", "local" if mode == "LOCAL" else "default"),
            "storage": storage_map.get(mode, "unknown"),
            "memory_types": len(VALID_TYPES),
            "api_version": "v1",
        })

    def do_OPTIONS(self):
        handle_cors(self)
