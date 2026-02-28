"""
router.py — Model seçimi ve Gemini AI ile yanıt üretimi.
"""
from __future__ import annotations

import os
from app.classifier import ClassificationResult

# ─── Model Tanımları ─────────────────────────────────────────────────────────

_COST_TABLE = {
    "gemini-2.5-flash": 0.00035,  # fast & medium
    "gemini-2.5-pro":   0.00350,  # quality / complex
}

_MODEL_LABELS = {
    "gemini-2.5-flash": "fast/multilingual (Gemini 2.5 Flash)",
    "gemini-2.5-pro":       "quality-model (Gemini 2.5 Pro)",
}


def select_model(c: ClassificationResult) -> str:
    if c.complexity == "high":
        return "gemini-2.5-pro"
    return "gemini-2.5-flash"


def model_cost_per_1k(model_name: str) -> float:
    return _COST_TABLE.get(model_name, 0.001)


def model_label(model_name: str) -> str:
    return _MODEL_LABELS.get(model_name, model_name)


# ─── Gemini İstemci ──────────────────────────────────────────────────────────

def _build_prompt(message: str, c: ClassificationResult, history: list[dict]) -> str:
    """System prompt + konuşma geçmişi + yeni mesaj birleştirme."""
    lang_hint = {"tr": "Turkish", "es": "Spanish", "en": "English"}.get(c.language, "English")

    system = (
        f"You are SMSAI, a helpful AI assistant. "
        f"The user is writing in {lang_hint} — reply in the SAME language. "
        f"Be concise, friendly, and direct. "
        f"Their intent is '{c.intent}' with '{c.complexity}' complexity."
    )

    history_text = ""
    if history:
        lines = []
        for h in history[-6:]:  # son 6 mesaj (3 tur)
            role = "User" if h["role"] == "user" else "Assistant"
            lines.append(f"{role}: {h['content']}")
        history_text = "\n".join(lines) + "\n"

    return f"{system}\n\n{history_text}User: {message}"


def generate_response(
    message: str,
    c: ClassificationResult,
    model: str,
    history: list[dict] | None = None,
) -> str:
    """Gemini API ile yanıt üret; API yoksa kural tabanlı fallback."""
    api_key = os.getenv("GEMINI_API_KEY", "")

    if api_key and api_key != "your_key_here":
        try:
            from google import genai  # type: ignore
            client = genai.Client(api_key=api_key)
            prompt = _build_prompt(message, c, history or [])
            response = client.models.generate_content(model=model, contents=prompt)
            return response.text
        except Exception as exc:
            return _fallback_response(message, c, model) + f"\n\n_(AI unavailable: {exc})_"

    return _fallback_response(message, c, model)


def _fallback_response(message: str, c: ClassificationResult, model: str) -> str:
    """Gerçek LLM yokken kural tabanlı yanıt (geliştirme/demo modu)."""
    prefix = {"tr": "Yanıt", "es": "Respuesta", "en": "Answer"}.get(c.language, "Answer")

    guidance = {
        "technical_support": (
            "TR: Sorununuzu çözmek için lütfen beklenen davranışı, gerçekleşen hatayı ve log çıktısını paylaşın.\n"
            "EN: Please share expected behavior, actual behavior, and logs."
        ),
        "pricing": (
            "TR: Küçük bir token bütçesiyle başlayıp kullanımı gözlemledikten sonra ölçeklendirmenizi öneririm.\n"
            "EN: Start with a small token budget and scale after observing usage."
        ),
        "complaint": (
            "TR: Yaşadığınız sorunu duymak üzüntü verici. Daha iyi bir deneyim sunabileceğiz.\n"
            "EN: We're sorry you had this experience. We'll work to improve."
        ),
        "feedback": (
            "TR: Geri bildiriminiz için teşekkürler! Önerileriniz incelenecek.\n"
            "EN: Thank you for your feedback! We'll consider your suggestion."
        ),
    }.get(c.intent, (
        "TR: İşte sorunuza kısa ve öz bir yanıt.\n"
        "EN: Here is a concise response tailored to your question."
    ))

    return (
        f"{prefix} [{model_label(model)}]:\n"
        f"{guidance}\n\n"
        f"─── Classification ───\n"
        f"• Language: {c.language} | Complexity: {c.complexity} | Intent: {c.intent}"
    )
