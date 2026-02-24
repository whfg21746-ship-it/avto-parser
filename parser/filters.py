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
    (r"версия\b.*\b(копи|реплик|android)", "копия/версия"),
    (r"лучшая\s+версия",         "копия (лучшая версия)"),
    (r"\bandroid\b",             "Android (не Apple)"),
    (r"\bандроид\b",             "Android (не Apple)"),

    # Repair / parts
    (r"на\s+запчасти",           "на запчасти"),
    (r"\bдонор\b",              "донор/запчасти"),
    (r"\bразбор\b",             "разбор/запчасти"),
    (r"icloud\s*(lock|залочен|заблокирован)", "iCloud lock"),

    # Bulk sellers
    (r"\bоптом\b",              "оптовая продажа"),
    (r"\bопт\b",                "оптовая продажа"),
    (r"\bпартия\b",             "оптовая партия"),
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


def should_reject_seller(
    seller_type: str,
    seller_closed_items: int,
    max_seller_items: int,
) -> tuple[bool, str]:
    """Check if seller should be rejected.

    Returns (should_reject, reason).
    """
    if seller_type == "shop":
        return True, "Company seller, not private"

    if seller_closed_items > max_seller_items:
        return True, f"Reseller: {seller_closed_items} closed ads (max: {max_seller_items})"

    return False, ""
