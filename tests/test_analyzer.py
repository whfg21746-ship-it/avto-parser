"""Tests for ai/analyzer.py — response validation and prompt building."""
import pytest

from ai.analyzer import validate_ai_response, _build_custom_instructions


class TestValidateAiResponse:
    def test_valid_response(self):
        resp = {
            "score": 7,
            "recommendation": "BUY",
            "comment": "Good deal",
            "defects": ["minor scratch"],
            "red_flags": [],
            "estimated_sell_price": 30000,
            "estimated_profit": 5000,
            "condition": "good",
        }
        result = validate_ai_response(resp)
        assert result is not None
        assert result["score"] == 7
        assert result["recommendation"] == "BUY"

    def test_missing_score(self):
        resp = {"recommendation": "BUY", "comment": "ok"}
        assert validate_ai_response(resp) is None

    def test_missing_recommendation(self):
        resp = {"score": 5, "comment": "ok"}
        assert validate_ai_response(resp) is None

    def test_missing_comment(self):
        resp = {"score": 5, "recommendation": "BUY"}
        assert validate_ai_response(resp) is None

    def test_invalid_score_clamped(self):
        resp = {"score": 15, "recommendation": "BUY", "comment": "ok"}
        result = validate_ai_response(resp)
        assert result["score"] == 0

    def test_negative_score_clamped(self):
        resp = {"score": -1, "recommendation": "BUY", "comment": "ok"}
        result = validate_ai_response(resp)
        assert result["score"] == 0

    def test_invalid_recommendation_defaults_skip(self):
        resp = {"score": 5, "recommendation": "MAYBE", "comment": "ok"}
        result = validate_ai_response(resp)
        assert result["recommendation"] == "SKIP"

    def test_defects_not_list_fixed(self):
        resp = {"score": 5, "recommendation": "BUY", "comment": "ok", "defects": "scratch"}
        result = validate_ai_response(resp)
        assert result["defects"] == []

    def test_numeric_fields_not_numeric_fixed(self):
        resp = {
            "score": 5, "recommendation": "BUY", "comment": "ok",
            "estimated_sell_price": "unknown",
            "estimated_profit": None,
        }
        result = validate_ai_response(resp)
        assert result["estimated_sell_price"] == 0
        assert result["estimated_profit"] == 0

    def test_valid_recommendations(self):
        for rec in ("BUY", "CHECK", "SKIP"):
            resp = {"score": 5, "recommendation": rec, "comment": "ok"}
            result = validate_ai_response(resp)
            assert result["recommendation"] == rec


class TestBuildCustomInstructions:
    def test_no_prompts(self):
        item = {"custom_prompt": None, "category_custom_prompt": None}
        assert _build_custom_instructions(item) == ""

    def test_item_prompt(self):
        item = {"custom_prompt": "Check battery", "category_custom_prompt": None}
        result = _build_custom_instructions(item)
        assert "Check battery" in result

    def test_category_prompt(self):
        item = {"custom_prompt": None, "category_custom_prompt": "Focus on screen"}
        result = _build_custom_instructions(item)
        assert "Focus on screen" in result

    def test_item_overrides_category(self):
        item = {"custom_prompt": "Item specific", "category_custom_prompt": "Category general"}
        result = _build_custom_instructions(item)
        assert "Item specific" in result
        assert "Category general" not in result

    def test_empty_strings(self):
        item = {"custom_prompt": "", "category_custom_prompt": ""}
        assert _build_custom_instructions(item) == ""
