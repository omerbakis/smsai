"""
classifier.py — Dil tespiti ve mesaj sınıflandırma.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ClassificationResult:
    language: str       # "tr" | "en" | "es" | "other"
    complexity: str     # "low" | "medium" | "high"
    intent: str         # "general_qa" | "technical_support" | "pricing" | "complaint" | "feedback"
    domain: str         # "general" | "technology" | "business"


# ─── Dil Tespiti ─────────────────────────────────────────────────────────────

_TR_PATTERN = re.compile(
    r"\b(merhaba|nasılsın|nasıl|teşekkür|şu|nedir|ne|bir|bu|için|fiyat|"
    r"sorun|yardım|çalışmıyor|hata|lütfen|evet|hayır|tamam|selam)\b",
    re.IGNORECASE,
)
_ES_PATTERN = re.compile(
    r"\b(hola|gracias|por qué|cómo|qué|está|estoy|problema|precio|ayuda)\b",
    re.IGNORECASE,
)
_TR_CHARS = re.compile(r"[ğüşıöçĞÜŞİÖÇ]")


def detect_language(text: str) -> str:
    if _TR_CHARS.search(text) or _TR_PATTERN.search(text.lower()):
        return "tr"
    if _ES_PATTERN.search(text.lower()):
        return "es"
    return "en"


# ─── Sınıflandırma ───────────────────────────────────────────────────────────

_TECH_KW = {
    "hata", "error", "bug", "çalışmıyor", "issue", "crash", "broken",
    "exception", "traceback", "failed", "fix", "debug", "sorun",
}
_PRICE_KW = {
    "fiyat", "price", "plan", "subscription", "cost", "ücret", "abonelik",
    "paket", "ödeme", "billing", "invoice",
}
_COMPLAINT_KW = {
    "şikayet", "complaint", "memnun değil", "kötü", "berbat", "rezalet",
    "disappointed", "terrible", "awful", "worst",
}
_FEEDBACK_KW = {
    "öneri", "suggestion", "feedback", "idea", "fikir", "geliştir",
    "improve", "feature request", "istek",
}


def classify_message(message: str) -> ClassificationResult:
    lower = message.lower()
    language = detect_language(message)

    # Intent belirleme — öncelik sırasıyla
    if any(k in lower for k in _COMPLAINT_KW):
        intent, domain = "complaint", "general"
    elif any(k in lower for k in _FEEDBACK_KW):
        intent, domain = "feedback", "general"
    elif any(k in lower for k in _TECH_KW):
        intent, domain = "technical_support", "technology"
    elif any(k in lower for k in _PRICE_KW):
        intent, domain = "pricing", "business"
    else:
        intent, domain = "general_qa", "general"

    # Karmaşıklık
    step_by_step = "adım adım" in lower or "step by step" in lower
    if len(message) > 300 or step_by_step or message.count("?") > 2:
        complexity = "high"
    elif len(message) > 120:
        complexity = "medium"
    else:
        complexity = "low"

    return ClassificationResult(
        language=language,
        complexity=complexity,
        intent=intent,
        domain=domain,
    )
