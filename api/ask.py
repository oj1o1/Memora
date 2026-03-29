"""POST /api/ask {question, project?} — AI-powered reasoning query."""

import os
from http.server import BaseHTTPRequestHandler
from memora.api_utils import get_memory, check_auth, send_json, read_body, handle_cors


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if not check_auth(self):
            return
        data = read_body(self)
        if data is None:
            return
        question = data.get("question", "")
        if not question:
            send_json(self, 400, {"error": "question is required"})
            return

        project = data.get("project", "")
        mem = get_memory()

        # Search for relevant decisions
        results = mem.recall(question, limit=10)
        if project:
            proj_results = mem.recall_by_project(project, limit=20)
            seen = {r["id"] for r in results}
            for r in proj_results:
                if r["id"] not in seen:
                    results.append(r)

        if not results:
            send_json(self, 200, {"answer": "No relevant decisions found.", "decisions": []})
            return

        # Build context
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

        # Synthesize answer with Groq
        try:
            from groq import Groq
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

        send_json(self, 200, {"answer": answer, "decisions": results[:5]})

    def do_OPTIONS(self):
        handle_cors(self)
