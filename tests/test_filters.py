"""Tests for parser/filters.py — instant reject patterns and seller checks."""
import pytest

from parser.filters import should_instant_reject, should_reject_model_pattern, should_reject_seller


class TestInstantReject:
    """Test INSTANT_REJECT_PATTERNS matching."""

    @pytest.mark.parametrize("title", [
        "iPhone 15 копия 1 в 1",
        "Реплика Apple Watch",
        "Samsung не оригинал",
        "Лучшая версия AirPods",
        "Наушники по мотивам Apple",
    ])
    def test_reject_copies(self, title: str):
        rejected, reason = should_instant_reject(title, "")
        assert rejected, f"Should reject copy: {title}"
        assert reason

    @pytest.mark.parametrize("title", [
        "iPhone на запчасти",
        "Ноутбук донор",
        "Телефон разбор",
        "Samsung не включается",
    ])
    def test_reject_parts(self, title: str):
        rejected, reason = should_instant_reject(title, "")
        assert rejected, f"Should reject parts: {title}"

    @pytest.mark.parametrize("title", [
        "iPhone iCloud lock",
        "Samsung Google залочен",
        "Xiaomi MI account lock",
        "Привязан к аккаунту владельца",
    ])
    def test_reject_locks(self, title: str):
        rejected, reason = should_instant_reject(title, "")
        assert rejected, f"Should reject lock: {title}"

    @pytest.mark.parametrize("title", [
        "Продаю оптом",
        "Наушники опт",
        "Партия iPhone",
        "Продажа от 10 штук",
    ])
    def test_reject_bulk(self, title: str):
        rejected, reason = should_instant_reject(title, "")
        assert rejected, f"Should reject bulk: {title}"

    @pytest.mark.parametrize("title", [
        "iPhone 15 Pro Max 256GB",
        "MacBook Air M2 отличное состояние",
        "PlayStation 5 Slim Digital",
        "Samsung Galaxy S24 Ultra",
        "AirPods Pro 2",
    ])
    def test_allow_normal_listings(self, title: str):
        rejected, _ = should_instant_reject(title, "")
        assert not rejected, f"Should allow: {title}"

    def test_reject_in_description(self):
        """Pattern in description should also trigger reject."""
        rejected, _ = should_instant_reject("iPhone 15", "Продаю копию, не оригинал")
        assert rejected

    def test_empty_input(self):
        rejected, _ = should_instant_reject("", "")
        assert not rejected


class TestSellerReject:
    """Test seller-based filtering."""

    def test_reject_shop(self):
        rejected, reason = should_reject_seller("shop", 0, 10)
        assert rejected
        assert "Коммерческий" in reason

    def test_reject_company(self):
        rejected, reason = should_reject_seller("company", 0, 10)
        assert rejected
        assert "Коммерческий" in reason

    def test_reject_high_active_items(self):
        rejected, reason = should_reject_seller("private", 20, 15)
        assert rejected
        assert "20" in reason
        assert "перекуп" in reason.lower()

    def test_reject_category_items(self):
        """Seller with >3 ads in the same category should be rejected."""
        rejected, reason = should_reject_seller(
            "private", 5, 15,
            seller_category_items=4, max_seller_category_items=3,
        )
        assert rejected
        assert "4" in reason
        assert "категори" in reason.lower()

    def test_category_items_zero_passes(self):
        """Zero category items (data unavailable) should pass."""
        rejected, _ = should_reject_seller(
            "private", 5, 15,
            seller_category_items=0, max_seller_category_items=3,
        )
        assert not rejected

    def test_category_items_exact_threshold(self):
        """Exactly at category threshold should pass (only > triggers)."""
        rejected, _ = should_reject_seller(
            "private", 5, 15,
            seller_category_items=3, max_seller_category_items=3,
        )
        assert not rejected

    def test_category_check_before_total(self):
        """Category check should trigger before total items check."""
        rejected, reason = should_reject_seller(
            "private", 20, 15,
            seller_category_items=5, max_seller_category_items=3,
        )
        assert rejected
        assert "категори" in reason.lower()

    def test_allow_private_few_items(self):
        rejected, _ = should_reject_seller("private", 3, 10)
        assert not rejected

    def test_allow_zero_items(self):
        """Zero active items (data unavailable) should pass."""
        rejected, _ = should_reject_seller("private", 0, 10)
        assert not rejected

    def test_exact_threshold(self):
        """Exactly at threshold should pass (only > triggers)."""
        rejected, _ = should_reject_seller("private", 10, 10)
        assert not rejected


class TestModelPattern:
    """Test model_pattern regex filtering."""

    def test_no_pattern_passes(self):
        rejected, _ = should_reject_model_pattern("iPhone 15", "", None)
        assert not rejected

    def test_empty_pattern_passes(self):
        rejected, _ = should_reject_model_pattern("iPhone 15", "", "")
        assert not rejected

    def test_matching_title(self):
        rejected, _ = should_reject_model_pattern("iPhone 15 Pro Max", "", r"iPhone 15 Pro")
        assert not rejected

    def test_matching_params(self):
        rejected, _ = should_reject_model_pattern("Телефон Apple", "256 ГБ, iPhone 15 Pro", r"iPhone 15")
        assert not rejected

    def test_not_matching(self):
        rejected, reason = should_reject_model_pattern("Samsung S24", "128 GB", r"iPhone 15")
        assert rejected
        assert "iPhone 15" in reason

    def test_case_insensitive(self):
        rejected, _ = should_reject_model_pattern("iphone 15 pro", "", r"iPhone 15")
        assert not rejected

    def test_invalid_regex_passes(self):
        """Invalid regex should not reject (fail-open)."""
        rejected, _ = should_reject_model_pattern("iPhone 15", "", r"[invalid")
        assert not rejected
