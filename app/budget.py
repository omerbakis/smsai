"""
budget.py — Token tahmini ve bütçe kontrolü.
"""
from __future__ import annotations

import os
from typing import Tuple

from app.storage import get_user_token_usage, get_global_token_usage

USER_TOKEN_LIMIT = int(os.getenv("USER_TOKEN_LIMIT", "6000"))
GLOBAL_TOKEN_LIMIT = int(os.getenv("GLOBAL_TOKEN_LIMIT", "120000"))


def estimate_tokens(text: str) -> int:
    """Kelime sayısı * 1.3 ile basit token tahmini."""
    return max(1, int(len(text.split()) * 1.3))


def assert_budget(user_id: str, request_tokens: int) -> Tuple[bool, str]:
    """Kullanıcı ve global limitleri kontrol eder."""
    user_used = get_user_token_usage(user_id)
    if user_used + request_tokens > USER_TOKEN_LIMIT:
        return False, "User token limit exceeded"

    global_used = get_global_token_usage()
    if global_used + request_tokens > GLOBAL_TOKEN_LIMIT:
        return False, "Global token budget exhausted"

    return True, ""
