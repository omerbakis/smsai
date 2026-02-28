"""
test_api.py — Ana chat akışı testleri (modüler mimari ile güncellenmiş).
"""
import sys
import os
import tempfile
from pathlib import Path

# Proje kökünü ekle
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Test için geçici DB yolu kullan
os.environ.setdefault("USER_TOKEN_LIMIT", "6000")
os.environ.setdefault("GLOBAL_TOKEN_LIMIT", "120000")

# Test DB'yi geçici konuma yönlendir
import app.storage as _s
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_s._DB_PATH = Path(_tmp_db.name)
_tmp_db.close()
_s.init_db()

from app.main import handle_chat


def test_chat_basic_turkish():
    status, data = handle_chat({"user_id": "u1", "message": "Merhaba, bu sistem nasıl çalışır?"})
    assert status == 200
    assert data["classification"]["language"] == "tr"
    assert data["selected_model"] in {"gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"}
    assert data["usage"]["total_tokens"] > 0


def test_chat_missing_fields():
    status, data = handle_chat({"user_id": "", "message": "hello"})
    assert status == 400
    assert "detail" in data


def test_chat_technical_intent():
    status, data = handle_chat({"user_id": "u3", "message": "I have a bug in my code, error on line 42"})
    assert status == 200
    assert data["classification"]["intent"] == "technical_support"


def test_chat_high_complexity():
    status, data = handle_chat({
        "user_id": "u4",
        "message": "Please explain step by step how to build a distributed system" * 3,
    })
    assert status in (200, 402)
    if status == 200:
        assert data["classification"]["complexity"] == "high"
        assert data["selected_model"] == "gemini-1.5-pro"


def test_budget_exceeded():
    big_message = "step by step " * 800
    got_limit = False
    for _ in range(10):
        status, _ = handle_chat({"user_id": "u2", "message": big_message})
        if status == 402:
            got_limit = True
            break
    assert got_limit
