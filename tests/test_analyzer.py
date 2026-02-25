"""Tests for ai/analyzer.py — response validation and category prompt resolution."""
import pytest

from ai.analyzer import validate_ai_response, _get_category_prompt, CATEGORY_PROMPTS


class TestValidateAiResponse:
    def test_valid_response(self):
        resp = {
            "verdict": "BUY",
            "score": 8,
            "comment": "Good deal",
            "product_identified": "iPhone 15 Pro 256GB",
            "condition_grade": "отличное",
            "listing_price": 45000,
            "estimated_buy_price": 43000,
            "estimated_sell_price": 55000,
            "expected_profit": 12000,
            "profit_percent": 28,
            "red_flags": [],
            "green_flags": ["реальные фото"],
            "action_advice": "Писать сразу",
            "scam_risk": "low",
        }
        result = validate_ai_response(resp)
        assert result is not None
        assert result["score"] == 8
        assert result["verdict"] == "BUY"

    def test_missing_verdict(self):
        resp = {"score": 5, "comment": "ok"}
        assert validate_ai_response(resp) is None

    def test_missing_score(self):
        resp = {"verdict": "BUY", "comment": "ok"}
        assert validate_ai_response(resp) is None

    def test_missing_comment(self):
        resp = {"verdict": "BUY", "score": 5}
        assert validate_ai_response(resp) is None

    def test_invalid_score_clamped(self):
        resp = {"score": 15, "verdict": "BUY", "comment": "ok"}
        result = validate_ai_response(resp)
        assert result["score"] == 0

    def test_negative_score_clamped(self):
        resp = {"score": -1, "verdict": "BUY", "comment": "ok"}
        result = validate_ai_response(resp)
        assert result["score"] == 0

    def test_invalid_verdict_defaults_skip(self):
        resp = {"score": 5, "verdict": "MAYBE", "comment": "ok"}
        result = validate_ai_response(resp)
        assert result["verdict"] == "SKIP"

    def test_valid_verdicts(self):
        for v in ("BUY", "CHECK", "SKIP"):
            resp = {"score": 5, "verdict": v, "comment": "ok"}
            result = validate_ai_response(resp)
            assert result["verdict"] == v

    def test_red_flags_not_list_fixed(self):
        resp = {"score": 5, "verdict": "BUY", "comment": "ok", "red_flags": "нет фото"}
        result = validate_ai_response(resp)
        assert result["red_flags"] == []

    def test_green_flags_not_list_fixed(self):
        resp = {"score": 5, "verdict": "BUY", "comment": "ok", "green_flags": "ok"}
        result = validate_ai_response(resp)
        assert result["green_flags"] == []

    def test_numeric_fields_not_numeric_fixed(self):
        resp = {
            "score": 5, "verdict": "BUY", "comment": "ok",
            "estimated_sell_price": "unknown",
            "expected_profit": None,
            "profit_percent": "N/A",
        }
        result = validate_ai_response(resp)
        assert result["estimated_sell_price"] == 0
        assert result["expected_profit"] == 0
        assert result["profit_percent"] == 0

    def test_scam_risk_invalid_defaults_medium(self):
        resp = {"score": 5, "verdict": "BUY", "comment": "ok", "scam_risk": "unknown"}
        result = validate_ai_response(resp)
        assert result["scam_risk"] == "medium"

    def test_scam_risk_valid_values(self):
        for risk in ("low", "medium", "high"):
            resp = {"score": 5, "verdict": "BUY", "comment": "ok", "scam_risk": risk}
            result = validate_ai_response(resp)
            assert result["scam_risk"] == risk

    def test_minimal_valid_response(self):
        resp = {"score": 5, "verdict": "CHECK", "comment": "Looks okay"}
        result = validate_ai_response(resp)
        assert result is not None
        assert result["expected_profit"] == 0
        assert result["red_flags"] == []
        assert result["green_flags"] == []


class TestGetCategoryPrompt:
    def test_exact_match(self):
        assert _get_category_prompt("iphone") is not None
        assert _get_category_prompt("macbook") is not None
        assert _get_category_prompt("gpu") is not None

    def test_case_insensitive(self):
        assert _get_category_prompt("iPhone") is not None
        assert _get_category_prompt("MACBOOK") is not None

    def test_alias_playstation(self):
        prompt = _get_category_prompt("playstation")
        assert prompt is not None
        assert "PlayStation" in prompt or "PS5" in prompt

    def test_alias_ps4(self):
        assert _get_category_prompt("ps4") is not None

    def test_alias_mac(self):
        assert _get_category_prompt("mac") is not None

    def test_alias_russian(self):
        assert _get_category_prompt("айфон") is not None
        assert _get_category_prompt("видеокарта") is not None

    def test_partial_match(self):
        # "iphone 15" contains "iphone"
        assert _get_category_prompt("iphone 15") is not None

    def test_unknown_category(self):
        assert _get_category_prompt("furniture") is None
        assert _get_category_prompt("") is None

    def test_all_categories_have_content(self):
        for key, prompt in CATEGORY_PROMPTS.items():
            assert len(prompt) > 50, f"Category {key} prompt too short"
