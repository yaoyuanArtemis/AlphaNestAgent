from __future__ import annotations

import json
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock
from urllib.parse import parse_qs, urlparse

from pydantic_ai.messages import ModelMessage

from agent_core import format_api_error, run_agent
from tools import economic_indicator

HOST = "127.0.0.1"
PORT = 8000

histories: dict[str, list[ModelMessage]] = {}
history_lock = Lock()


class AgentRequestHandler(BaseHTTPRequestHandler):
    def _send_json(self, status_code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length == 0:
            return {}

        raw_body = self.rfile.read(content_length)
        return json.loads(raw_body.decode("utf-8"))

    def do_OPTIONS(self) -> None:
        self._send_json(204, {})

    def do_GET(self) -> None:
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        if path == "/health":
            self._send_json(200, {"ok": True})
            return

        if path == "/macro":
            self._handle_macro(parsed_url.query)
            return

        self._send_json(404, {"error": "Not found"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path

        if path == "/chat":
            self._handle_chat()
            return

        if path == "/reset":
            self._handle_reset()
            return

        self._send_json(404, {"error": "Not found"})

    def _handle_chat(self) -> None:
        try:
            payload = self._read_json()
            message = str(payload.get("message", "")).strip()
            session_id = str(payload.get("session_id") or uuid.uuid4())

            if not message:
                self._send_json(400, {"error": "message is required"})
                return

            with history_lock:
                history = list(histories.get(session_id, []))

            reply = run_agent(message, history)

            with history_lock:
                histories[session_id] = reply.history

            self._send_json(
                200,
                {
                    "session_id": session_id,
                    "reply": reply.output,
                },
            )
        except Exception as error:
            self._send_json(500, {"error": format_api_error(error)})

    def _handle_reset(self) -> None:
        payload = self._read_json()
        session_id = str(payload.get("session_id", "")).strip()

        if session_id:
            with history_lock:
                histories.pop(session_id, None)

        self._send_json(200, {"ok": True})

    def _handle_macro(self, query: str) -> None:
        params = parse_qs(query)
        indicator = params.get("indicator", ["CPI"])[0]
        interval = params.get("interval", ["monthly"])[0]

        try:
            limit = int(params.get("limit", ["120"])[0])
        except ValueError:
            limit = 120

        result = economic_indicator(indicator=indicator, interval=interval, limit=limit)
        if "error_type" in result:
            self._send_json(400, {"error": result})
            return

        self._send_json(200, result)


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), AgentRequestHandler)
    print(f"AlphaNestAgent API running at http://{HOST}:{PORT}")
    print("Endpoints: GET /health, POST /chat, POST /reset")
    server.serve_forever()


if __name__ == "__main__":
    main()
