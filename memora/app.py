"""
Flask web API and dashboard server for Memora.
Run with: python -m memora.app
"""

import os
from dotenv import load_dotenv
from typing import Optional

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from memora.memory import MemoraMemory
from memora.store import VALID_TYPES

load_dotenv()

app = Flask(__name__, static_folder=None)
CORS(app)

_memory: Optional[MemoraMemory] = None


def get_memory() -> MemoraMemory:
    global _memory
    if _memory is None:
        _memory = MemoraMemory(
            db_path=os.getenv("MEMORA_DB_PATH"),
            api_key=os.getenv("GROQ_API_KEY"),
        )
    return _memory


@app.route("/")
def landing():
    landing_dir = os.path.join(os.path.dirname(__file__), "landing")
    return send_from_directory(landing_dir, "index.html")


@app.route("/dashboard")
def dashboard():
    dashboard_dir = os.path.join(os.path.dirname(__file__), "dashboard")
    return send_from_directory(dashboard_dir, "index.html")


@app.route("/api/decisions", methods=["GET"])
def api_list_decisions():
    project = request.args.get("project", "")
    agent = request.args.get("agent", "")
    tag = request.args.get("tag", "")
    dtype = request.args.get("type", "")
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))
    decisions = get_memory().list_all(project=project, agent=agent, tag=tag, type=dtype, limit=limit, offset=offset)
    return jsonify(decisions)


@app.route("/api/decisions", methods=["POST"])
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
def api_search_decisions():
    query = request.args.get("q", "")
    limit = int(request.args.get("limit", 20))
    if not query:
        return jsonify({"error": "query parameter 'q' is required"}), 400
    results = get_memory().recall(query, limit=limit)
    return jsonify(results)


@app.route("/api/decisions/<decision_id>", methods=["GET"])
def api_get_decision(decision_id: str):
    result = get_memory().get_decision(decision_id)
    if result is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(result)


@app.route("/api/decisions/<decision_id>", methods=["DELETE"])
def api_delete_decision(decision_id: str):
    ok = get_memory().delete_decision(decision_id)
    if not ok:
        return jsonify({"error": "not found"}), 404
    return jsonify({"deleted": True, "id": decision_id})


@app.route("/api/decisions/<decision_id>/links", methods=["GET"])
def api_get_links(decision_id: str):
    related = get_memory().get_related(decision_id)
    return jsonify(related)


@app.route("/api/decisions/link", methods=["POST"])
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
def api_stats():
    project = request.args.get("project", "")
    return jsonify(get_memory().stats(project=project))


@app.route("/api/why", methods=["POST"])
def api_why():
    data = request.get_json()
    if not data or "question" not in data:
        return jsonify({"error": "question is required"}), 400

    question = data["question"]
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
def api_timeline():
    project = request.args.get("project", "")
    limit = int(request.args.get("limit", 100))
    decisions = get_memory().list_all(project=project, limit=limit)

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
