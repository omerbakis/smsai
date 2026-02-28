"""
test_classifier.py — Dil tespiti ve sınıflandırma unit testleri.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.classifier import detect_language, classify_message


def test_detect_turkish_by_keyword():
    assert detect_language("Merhaba nasılsın") == "tr"


def test_detect_turkish_by_chars():
    assert detect_language("Şu an bir sorun var, çalışmıyor") == "tr"


def test_detect_english():
    assert detect_language("Hello, how are you doing today?") == "en"


def test_detect_spanish():
    assert detect_language("Hola, cómo estás hoy?") == "es"


def test_intent_technical():
    c = classify_message("There is a bug in the system, error thrown")
    assert c.intent == "technical_support"
    assert c.domain == "technology"


def test_intent_pricing():
    c = classify_message("What is the price of the subscription plan?")
    assert c.intent == "pricing"
    assert c.domain == "business"


def test_intent_complaint():
    c = classify_message("This is terrible, I am so disappointed")
    assert c.intent == "complaint"


def test_intent_feedback():
    c = classify_message("Here is a suggestion to improve the system")
    assert c.intent == "feedback"


def test_complexity_low():
    c = classify_message("Hi!")
    assert c.complexity == "low"


def test_complexity_high():
    c = classify_message("Please explain step by step how this works in detail.")
    assert c.complexity == "high"


def test_complexity_medium():
    # message must be > 120 chars to trigger medium
    msg = "Can you explain in some detail how machine learning algorithms generally work and what are the main types of models used?"
    assert len(msg) > 120
    c = classify_message(msg)
    assert c.complexity == "medium"
