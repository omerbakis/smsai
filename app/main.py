from __future__ import annotations

import json
import re
import time
from collections import defaultdict
from dataclasses import asdict, dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, List, Tuple

USER_TOKEN_LIMIT = 6_000
GLOBAL_TOKEN_LIMIT = 120_000
ROOT = Path(__file__).resolve().parent.parent


@dataclass
class ClassificationResult:
    language: str
    complexity: str
    intent: str
    domain: str


usage_log: List[dict] = []
user_token_usage: Dict[str, int] = defaultdict(int)
global_token_usage = 0


def estimate_tokens(text: str) -> int:
    words = len(text.split())
    return max(1, int(words * 1.3))


def detect_language(text: str) -> str:
    lower = text.lower()
    if re.search(r"\b(merhaba|nasılsın|teşekkür|şu|nedir|nasıl)\b", lower):
        return "tr"
    if re.search(r"\b(hola|gracias|por qué|cómo)\b", lower):
        return "es"
    return "en"


def classify_message(message: str) -> ClassificationResult:
    lower = message.lower()
    language = detect_language(message)

    if any(k in lower for k in ["hata", "error", "bug", "çalışmıyor", "issue"]):
        intent = "technical_support"
        domain = "technology"
    elif any(k in lower for k in ["fiyat", "price", "plan", "subscription"]):
        intent = "pricing"
        domain = "business"
    else:
        intent = "general_qa"
        domain = "general"

    if len(message) > 300 or "adım adım" in lower or "step by step" in lower:
        complexity = "high"
    elif len(message) > 120:
        complexity = "medium"
    else:
        complexity = "low"

    return ClassificationResult(language=language, complexity=complexity, intent=intent, domain=domain)


def select_model(c: ClassificationResult) -> str:
    if c.complexity == "high":
        return "quality-model-v2"
    if c.language not in {"en", "tr"}:
        return "multilingual-model-v1"
    return "fast-model-v1"


def model_cost_per_1k(model_name: str) -> float:
    return {
        "fast-model-v1": 0.0006,
        "multilingual-model-v1": 0.0012,
        "quality-model-v2": 0.003,
    }.get(model_name, 0.001)


def generate_response(message: str, c: ClassificationResult, model: str) -> str:
    prefix = {"tr": "Yanıt", "es": "Respuesta", "en": "Answer"}.get(c.language, "Answer")

    if c.intent == "technical_support":
        guidance = "Please share expected behavior, actual behavior, and logs for faster support."
    elif c.intent == "pricing":
        guidance = "Start with a small token budget and scale after observing usage."
    else:
        guidance = "Here is a concise response tailored to your question."

    return (
        f"{prefix} ({model}): {guidance}\n"
        f"Detected language={c.language}, complexity={c.complexity}, intent={c.intent}.\n"
        f"Question summary: {message[:220]}"
    )


def assert_budget(user_id: str, request_tokens: int) -> Tuple[bool, str]:
    if user_token_usage[user_id] + request_tokens > USER_TOKEN_LIMIT:
        return False, "User token limit exceeded"
    if global_token_usage + request_tokens > GLOBAL_TOKEN_LIMIT:
        return False, "Global token budget exhausted"
    return True, ""


def handle_chat(payload: dict) -> Tuple[int, dict]:
    global global_token_usage

    user_id = str(payload.get("user_id", "")).strip()
    message = str(payload.get("message", "")).strip()
    if not user_id or not message:
        return 400, {"detail": "user_id and message are required"}

    c = classify_message(message)
    model = select_model(c)

    input_tokens = estimate_tokens(message)
    reserved_output = 180 if c.complexity == "high" else 90
    ok, detail = assert_budget(user_id, input_tokens + reserved_output)
    if not ok:
        return 402, {"detail": detail}

    answer = generate_response(message, c, model)
    output_tokens = estimate_tokens(answer)
    total = input_tokens + output_tokens

    ok, detail = assert_budget(user_id, total)
    if not ok:
        return 402, {"detail": detail}

    user_token_usage[user_id] += total
    global_token_usage += total

    usage = {
        "user_id": user_id,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total,
        "estimated_cost_usd": round((total / 1000) * model_cost_per_1k(model), 6),
        "timestamp": time.time(),
    }
    usage_log.append(usage)

    return 200, {
        "answer": answer,
        "classification": asdict(c),
        "selected_model": model,
        "usage": usage,
        "budgets": {
            "user_tokens_used": user_token_usage[user_id],
            "user_tokens_left": USER_TOKEN_LIMIT - user_token_usage[user_id],
            "global_tokens_used": global_token_usage,
            "global_tokens_left": GLOBAL_TOKEN_LIMIT - global_token_usage,
        },
    }


class AppHandler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: dict | list) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
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

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/":
            return self._send_file(ROOT / "static" / "index.html", "text/html; charset=utf-8")
        if self.path == "/api/usage":
            return self._send_json(200, usage_log[-200:])
        self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/chat":
            self.send_error(404)
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length)
            payload = json.loads(raw_body.decode("utf-8"))
        except (ValueError, json.JSONDecodeError):
            self._send_json(400, {"detail": "Invalid JSON payload"})
            return

        status, response = handle_chat(payload)
        self._send_json(status, response)


def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    server = ThreadingHTTPServer((host, port), AppHandler)
    print(f"Server running at http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run_server()
