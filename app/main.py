"""
main.py — SMSAI HTTP sunucusu. Tüm iş mantığı ayrı modüllerde.
"""
from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Tuple

# Proje kökünü path'e ekle (doğrudan çalıştırma için)
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from app.classifier import classify_message
from app.router import select_model, model_cost_per_1k, model_label, generate_response
from app.storage import (
    init_db, log_usage, get_usage_log, get_stats,
    save_message, get_history,
    get_user_token_usage, get_global_token_usage,
)
from app.budget import estimate_tokens, assert_budget, USER_TOKEN_LIMIT, GLOBAL_TOKEN_LIMIT

# Veritabanını başlat
init_db()


# ─── Chat İşleyici ────────────────────────────────────────────────────────────

def handle_chat(payload: dict) -> Tuple[int, dict]:
    user_id = str(payload.get("user_id", "")).strip()
    message = str(payload.get("message", "")).strip()
    if not user_id or not message:
        return 400, {"detail": "user_id and message are required"}

    c = classify_message(message)
    model = select_model(c)

    input_tokens = estimate_tokens(message)
    reserved_output = 300 if c.complexity == "high" else 150
    ok, detail = assert_budget(user_id, input_tokens + reserved_output)
    if not ok:
        return 402, {"detail": detail}

    # Konuşma geçmişini çek
    history = get_history(user_id, limit=10)

    # Yanıt üret
    answer = generate_response(message, c, model, history)
    output_tokens = estimate_tokens(answer)
    total = input_tokens + output_tokens

    # Budget ikinci kontrol (gerçek output sonrası)
    ok, detail = assert_budget(user_id, total)
    if not ok:
        return 402, {"detail": detail}

    cost = round((total / 1000) * model_cost_per_1k(model), 6)

    # Kayıt
    save_message(user_id, "user", message)
    save_message(user_id, "assistant", answer)
    log_usage(
        user_id=user_id,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total,
        estimated_cost_usd=cost,
        language=c.language,
        intent=c.intent,
        complexity=c.complexity,
    )

    user_used = get_user_token_usage(user_id)
    global_used = get_global_token_usage()

    return 200, {
        "answer": answer,
        "classification": {
            "language": c.language,
            "complexity": c.complexity,
            "intent": c.intent,
            "domain": c.domain,
        },
        "selected_model": model,
        "model_label": model_label(model),
        "usage": {
            "user_id": user_id,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total,
            "estimated_cost_usd": cost,
        },
        "budgets": {
            "user_tokens_used": user_used,
            "user_tokens_left": max(0, USER_TOKEN_LIMIT - user_used),
            "user_token_limit": USER_TOKEN_LIMIT,
            "global_tokens_used": global_used,
            "global_tokens_left": max(0, GLOBAL_TOKEN_LIMIT - global_used),
        },
    }


# ─── HTTP Sunucu ──────────────────────────────────────────────────────────────

class AppHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # suppress default logs
        pass

    def _send_json(self, status: int, payload: dict | list) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path, content_type: str) -> None:
        if not path.exists() or not path.is_file():
            self.send_error(404)
            return
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)
            return json.loads(raw.decode("utf-8"))
        except (ValueError, json.JSONDecodeError):
            return None

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/":
            return self._send_file(ROOT / "static" / "index.html", "text/html; charset=utf-8")
        if self.path == "/api/usage":
            return self._send_json(200, get_usage_log(200))
        if self.path == "/api/stats":
            return self._send_json(200, get_stats())
        if self.path.startswith("/api/history/"):
            uid = self.path.split("/api/history/", 1)[-1]
            return self._send_json(200, get_history(uid, 50))
        self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/chat":
            self.send_error(404)
            return
        payload = self._read_json_body()
        if payload is None:
            self._send_json(400, {"detail": "Invalid JSON payload"})
            return
        status, response = handle_chat(payload)
        self._send_json(status, response)


def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    server = ThreadingHTTPServer((host, port), AppHandler)
    print(f"🚀 SMSAI running at http://{host}:{port}")
    print(f"   Chat UI   → http://{host}:{port}/")
    print(f"   Chat API  → POST http://{host}:{port}/api/chat")
    print(f"   Usage     → GET  http://{host}:{port}/api/usage")
    print(f"   Stats     → GET  http://{host}:{port}/api/stats")
    print(f"   History   → GET  http://{host}:{port}/api/history/{{user_id}}")
    server.serve_forever()


if __name__ == "__main__":
    run_server()
