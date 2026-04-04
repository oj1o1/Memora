"""
Flask web API and dashboard server for Memora.
Run with: python -m memora.app
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from typing import Optional

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from functools import wraps

from memora.memory import MemoraMemory
from memora.store import VALID_TYPES
from memora.api_limits import (
    parse_limit, parse_offset, paginated,
    MAX_QUERY_LENGTH, MAX_SEARCH_RESULTS, MAX_REQUEST_BYTES,
    RateLimiter,
)

# Load .env from the memora package directory
load_dotenv(Path(__file__).parent / ".env")

app = Flask(__name__, static_folder=None)
CORS(app)

_rate_limiter = RateLimiter()


def require_auth(f):
    """Protect an endpoint with Bearer token auth.

    Only enforced when MEMORA_API_KEY is set on the server.
    If no key is configured, all requests are allowed (local dev mode).
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        server_key = os.getenv("MEMORA_API_KEY", "")
        if not server_key:
            return f(*args, **kwargs)
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing Authorization header"}), 401
        token = auth_header[7:]
        if token != server_key:
            return jsonify({"error": "Invalid API key"}), 401
        return f(*args, **kwargs)
    return decorated


@app.before_request
def check_request_limits():
    """Reject oversized request bodies and rate-limit by IP."""
    # Request size protection
    content_length = request.content_length
    if content_length and content_length > MAX_REQUEST_BYTES:
        return jsonify({"error": "Request body too large", "max_bytes": MAX_REQUEST_BYTES}), 413

    # Rate limiting
    client_ip = request.remote_addr or "unknown"
    if not _rate_limiter.is_allowed(client_ip):
        return jsonify({"error": "Rate limit exceeded. Try again later."}), 429


_memory: Optional[MemoraMemory] = None


def get_memory() -> MemoraMemory:
    global _memory
    if _memory is None:
        _memory = MemoraMemory(
            db_path=os.getenv("MEMORA_DB_PATH"),
            api_key=os.getenv("GROQ_API_KEY"),
        )
    return _memory


# Serve from the project root landing/ and dashboard/ directories
# (same files Vercel deploys — single source of truth)
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


@app.route("/")
def landing():
    return send_from_directory(os.path.join(_project_root, "landing"), "index.html")


@app.route("/dashboard")
def dashboard():
    return send_from_directory(os.path.join(_project_root, "dashboard"), "index.html")


@app.route("/api/backend", methods=["GET"])
def api_backend():
    from memora.memory_backend import get_backend_mode
    mode = get_backend_mode()
    storage_map = {"LOCAL": "sqlite", "REMOTE": "api", "TURSO": "cloud"}
    return jsonify({
        "mode": mode,
        "workspace": os.getenv("MEMORA_WORKSPACE", "local" if mode == "LOCAL" else "default"),
        "storage": storage_map.get(mode, "unknown"),
        "memory_types": len(VALID_TYPES),
        "api_version": "v1",
    })


@app.route("/api/decisions", methods=["GET"])
@require_auth
def api_list_decisions():
    project = request.args.get("project", "")
    agent = request.args.get("agent", "")
    tag = request.args.get("tag", "")
    dtype = request.args.get("type", "")
    workspace = request.args.get("workspace", "")
    limit = parse_limit(request.args.get("limit"))
    offset = parse_offset(request.args.get("offset"))
    decisions = get_memory().list_all(project=project, agent=agent, tag=tag, type=dtype, limit=limit, offset=offset, workspace=workspace)
    return jsonify(paginated(decisions, limit, offset))


@app.route("/api/decisions", methods=["POST"])
@require_auth
def api_create_decision():
    data = request.get_json()
    if not data or "summary" not in data or "reasoning" not in data:
        return jsonify({"error": "summary and reasoning are required"}), 400
    result = get_memory().record(
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
    return jsonify(result), 201


@app.route("/api/decisions/search", methods=["GET"])
@require_auth
def api_search_decisions():
    query = request.args.get("q", "")
    if not query:
        return jsonify({"error": "query parameter 'q' is required"}), 400
    if len(query) > MAX_QUERY_LENGTH:
        return jsonify({"error": f"Query too long (max {MAX_QUERY_LENGTH} chars)"}), 400
    limit = parse_limit(request.args.get("limit"), default=20)
    limit = min(limit, MAX_SEARCH_RESULTS)
    results = get_memory().recall(query, limit=limit)
    return jsonify(paginated(results, limit, 0))


@app.route("/api/decisions/<decision_id>", methods=["GET"])
@require_auth
def api_get_decision(decision_id: str):
    result = get_memory().get_decision(decision_id)
    if result is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(result)


@app.route("/api/decisions/<decision_id>", methods=["DELETE"])
@require_auth
def api_delete_decision(decision_id: str):
    ok = get_memory().delete_decision(decision_id)
    if not ok:
        return jsonify({"error": "not found"}), 404
    return jsonify({"deleted": True, "id": decision_id})


@app.route("/api/decisions/<decision_id>/links", methods=["GET"])
@require_auth
def api_get_links(decision_id: str):
    related = get_memory().get_related(decision_id)
    return jsonify(related)


@app.route("/api/decisions/link", methods=["POST"])
@require_auth
def api_link_decisions():
    data = request.get_json()
    if not data or "from_id" not in data or "to_id" not in data:
        return jsonify({"error": "from_id and to_id are required"}), 400
    result = get_memory().link_decisions(
        from_id=data["from_id"],
        to_id=data["to_id"],
        relation=data.get("relation", "related"),
    )
    return jsonify(result), 201


@app.route("/api/decisions/extract", methods=["POST"])
@require_auth
def api_extract_decisions():
    data = request.get_json()
    if not data or "text" not in data:
        return jsonify({"error": "text is required"}), 400
    results = get_memory().extract_and_store(
        text=data["text"],
        context=data.get("context", ""),
        project=data.get("project", ""),
        agent=data.get("agent", ""),
        source="api-extract",
    )
    return jsonify(results), 201


@app.route("/api/stats", methods=["GET"])
@require_auth
def api_stats():
    project = request.args.get("project", "")
    return jsonify(get_memory().stats(project=project))


@app.route("/api/why", methods=["POST"])
@require_auth
def api_why():
    data = request.get_json()
    if not data or "question" not in data:
        return jsonify({"error": "question is required"}), 400

    question = data["question"]
    if len(question) > MAX_QUERY_LENGTH:
        return jsonify({"error": f"Question too long (max {MAX_QUERY_LENGTH} chars)"}), 400

    project = data.get("project", "")

    # Search for relevant decisions
    results = get_memory().recall(question, limit=10)
    if project:
        proj_results = get_memory().recall_by_project(project, limit=20)
        seen = {r["id"] for r in results}
        for r in proj_results:
            if r["id"] not in seen:
                results.append(r)

    if not results:
        return jsonify({"answer": "No relevant decisions found.", "decisions": []})

    # Build context from decisions
    context_lines = []
    for d in results[:10]:
        line = f"[{d.get('type', 'DECISION')}] {d['summary']}: {d['reasoning']}"
        if d.get("alternatives"):
            line += f" (alternatives rejected: {', '.join(d['alternatives'])})"
        if d.get("agent"):
            line += f" (by {d['agent']})"
        line += f" [{d.get('created_at', '')[:10]}]"
        context_lines.append(line)

    context_block = "\n".join(context_lines)

    # Use Groq to synthesize an answer
    try:
        from groq import Groq
        import os
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=512,
            messages=[
                {"role": "system", "content": (
                    "You are Memora, an AI that explains why development decisions changed. "
                    "Given a set of recorded decisions and a user question, provide a concise, "
                    "specific answer. Reference session dates, engineers, and exact values. "
                    "Format: start with the direct answer, then add key details. Keep it under 4 sentences."
                )},
                {"role": "user", "content": f"Decisions:\n{context_block}\n\nQuestion: {question}"},
            ],
        )
        answer = response.choices[0].message.content.strip()
    except Exception as e:
        answer = f"Could not generate answer: {e}"

    return jsonify({"answer": answer, "decisions": results[:5]})


@app.route("/api/timeline", methods=["GET"])
@require_auth
def api_timeline():
    project = request.args.get("project", "")
    workspace = request.args.get("workspace", "")
    limit = parse_limit(request.args.get("limit"))
    decisions = get_memory().list_all(project=project, workspace=workspace, limit=limit)

    # Group by date as "sessions"
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
    return jsonify(timeline)


def main():
    host = os.getenv("MEMORA_HOST", "127.0.0.1")
    port = int(os.getenv("MEMORA_PORT", "8377"))
    app.run(host=host, port=port, debug=True)


if __name__ == "__main__":
    main()
