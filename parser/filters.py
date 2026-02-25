"""Pre-AI filtering: instant-reject patterns and seller checks.

These filters run BEFORE the GPT call to save API money and reject
obvious junk (copies, fakes, parts, bulk sellers).
"""

import logging
import re

logger = logging.getLogger(__name__)

# fmt: off
INSTANT_REJECT_PATTERNS: list[tuple[str, str]] = [
    # Copies / fakes
    (r"копи[яи]",                "копия/реплика"),
    (r"реплик[аи]",              "копия/реплика"),
    (r"не\s*оригинал",           "не оригинал"),
    (r"1\s*в\s*1",               "копия 1 в 1"),
    (r"лучшая\s+версия",         "копия (лучшая версия)"),
    (r"по\s+мотивам",            "подделка (по мотивам)"),

    # Repair / parts
    (r"на\s+запчасти",           "на запчасти"),
    (r"\bдонор\b",              "донор/запчасти"),
    (r"\bразбор\b",             "разбор/запчасти"),
    (r"не\s*включается",        "не включается"),

    # Account locks
    (r"icloud\s*(lock|залочен|заблокирован)", "iCloud lock"),
    (r"google\s*(lock|залочен)",              "Google lock"),
    (r"mi\s*account\s*(lock|залочен)",        "MI account lock"),
    (r"привязан\s+к\s+аккаунту",             "привязан к аккаунту"),

    # Bulk sellers
    (r"\bоптом\b",              "оптовая продажа"),
    (r"\bопт\b",                "оптовая продажа"),
    (r"\bпартия\b",             "оптовая партия"),
    (r"от\s+\d+\s+штук",       "оптовая продажа"),
]
# fmt: on

_COMPILED_PATTERNS = [(re.compile(p, re.IGNORECASE), label) for p, label in INSTANT_REJECT_PATTERNS]


def should_instant_reject(title: str, description: str) -> tuple[bool, str]:
    """Check if listing should be rejected without AI analysis.

    Returns (should_reject, reason).
    """
    text = f"{title} {description}".lower()
    for pattern, label in _COMPILED_PATTERNS:
        if pattern.search(text):
            reason = f"Auto-reject: '{label}' matched"
            return True, reason
    return False, ""


def should_reject_model_pattern(
    title: str, params_str: str, model_pattern: str | None,
) -> tuple[bool, str]:
    """Check if ad matches the required model_pattern regex.

    If model_pattern is set and neither the title nor params match it,
    the ad is rejected. If model_pattern is None/empty, always passes.

    Returns (should_reject, reason).
    """
    if not model_pattern:
        return False, ""

    text = f"{title} {params_str}".lower()
    try:
        if re.search(model_pattern, text, re.IGNORECASE):
            return False, ""
    except re.error as e:
        logger.warning("Invalid model_pattern regex %r: %s", model_pattern, e)
        return False, ""

    return True, f"Model pattern '{model_pattern}' not matched"


def should_reject_seller(
    seller_type: str,
    seller_active_items: int,
    max_seller_items: int,
) -> tuple[bool, str]:
    """Check if seller should be rejected.

    Filters by number of currently active listings (not closed/completed).
    Returns (should_reject, reason).
    """
    if seller_type == "shop":
        return True, "Company seller, not private"

    if seller_active_items > max_seller_items:
        return True, f"Reseller: {seller_active_items} active ads (max: {max_seller_items})"

    return False, ""
