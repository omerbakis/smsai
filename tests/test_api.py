import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import handle_chat


def test_chat_route_and_usage_tracking() -> None:
    status, data = handle_chat({"user_id": "u1", "message": "Merhaba bu sistem nasıl çalışır?"})
    assert status == 200
    assert data["classification"]["language"] == "tr"
    assert data["selected_model"] in {
        "fast-model-v1",
        "multilingual-model-v1",
        "quality-model-v2",
    }
    assert data["usage"]["total_tokens"] > 0


def test_budget_exceeded_user_limit() -> None:
    big_message = "step by step " * 800
    got_limit = False
    for _ in range(10):
        status, _ = handle_chat({"user_id": "u2", "message": big_message})
        if status == 402:
            got_limit = True
            break

    assert got_limit
