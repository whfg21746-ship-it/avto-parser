"""Model pattern matching and storage extraction for Avito listings.

Matches listing titles against item model patterns and extracts storage
information from titles and listing attributes.
"""

import re
from typing import Any

UPGRADE_WORDS = {"max", "plus", "pro", "ultra", "mini", "se", "air"}


def model_matches(pattern: str, title: str) -> bool:
    """Check if a listing title matches a model pattern.

    'iphone 15 pro' matches 'iPhone 15 Pro 256GB Черный'
    'iphone 15 pro' does NOT match 'iPhone 15 Pro Max 256GB'
    'iphone 15 pro max' DOES match 'iPhone 15 Pro Max 256GB'
    """
    title_lower = title.lower()
    pattern_lower = pattern.lower()

    pattern_words = pattern_lower.split()
    title_words = title_lower.split()

    if not all(word in title_words for word in pattern_words):
        return False

    for word in UPGRADE_WORDS:
        if word in title_words and word not in pattern_words:
            return False

    return True


def parse_storage_value(text: str) -> int | None:
    """Parse a storage value string like '256 GB' or '1 TB' to integer GB."""
    text = text.lower().strip()

    tb_match = re.search(r'(\d+)\s*(?:tb|тб)', text)
    if tb_match:
        return int(tb_match.group(1)) * 1024

    gb_match = re.search(r'(\d+)\s*(?:gb|гб)', text)
    if gb_match:
        return int(gb_match.group(1))

    return None


def extract_storage_from_listing(title: str, listing_params: dict[str, Any] | None = None) -> int | None:
    """Extract storage (GB) from listing title or attributes.

    Looks for patterns like:
    - "256gb", "256 gb", "256гб", "256 гб"
    - "1tb", "1 tb", "1тб", "1 тб" (convert to 1024 GB)
    """
    if listing_params:
        for value in listing_params.values():
            value_lower = str(value).lower()
            if any(marker in value_lower for marker in ('gb', 'гб', 'tb', 'тб')):
                result = parse_storage_value(value_lower)
                if result:
                    return result

    title_lower = title.lower()

    tb_match = re.search(r'(\d+)\s*(?:tb|тб)', title_lower)
    if tb_match:
        return int(tb_match.group(1)) * 1024

    gb_match = re.search(r'(\d+)\s*(?:gb|гб)', title_lower)
    if gb_match:
        return int(gb_match.group(1))

    return None


def match_listing_to_item(
    listing_title: str,
    listing_params: dict[str, Any] | None,
    items: list[dict],
) -> dict | None:
    """Match a listing to a specific item (model+storage) from our database.

    Uses listing title + listing attributes from the search results response.
    Returns the matched Item dict or None if no match.
    """
    matched_items = []
    for item in items:
        pattern = item["model_pattern"]
        if model_matches(pattern, listing_title):
            matched_items.append(item)

    if not matched_items:
        return None

    matched_items.sort(key=lambda x: len(x["model_pattern"]), reverse=True)
    best_match = matched_items[0]

    if best_match.get("storage_gb") is not None:
        storage = extract_storage_from_listing(listing_title, listing_params)
        if storage == best_match["storage_gb"]:
            return best_match
        for item in matched_items:
            if item.get("storage_gb") is not None and item["storage_gb"] == storage:
                return item
        return None

    return best_match


def generate_model_pattern(name: str) -> str:
    """Auto-generate a model_pattern from a display name.

    Strips storage info (e.g., '256GB', '1TB'), 'Wi-Fi', year, RAM info,
    and lowercases.
    """
    pattern = name.lower()
    # Remove RAM/storage combos like "8/256GB", "16/512GB" first
    pattern = re.sub(r'\d+/\d+\s*(?:gb|гб|tb|тб)?\b', '', pattern)
    # Remove standalone storage like "256GB", "1TB"
    pattern = re.sub(r'\d+\s*(?:gb|гб|tb|тб)\b', '', pattern)
    pattern = re.sub(r'\bwi-?fi\b', '', pattern)
    pattern = re.sub(r'\b20\d{2}\b', '', pattern)
    pattern = re.sub(r'\busb-?c\b', '', pattern)
    pattern = re.sub(r'\blightning\b', '', pattern)
    pattern = re.sub(r'\banc\b', '', pattern)
    pattern = re.sub(r'\s+', ' ', pattern).strip()
    return pattern


def extract_storage_from_name(name: str) -> int | None:
    """Extract storage from a product name like 'iPhone 15 Pro 256GB'."""
    lower = name.lower()

    tb_match = re.search(r'(\d+)\s*(?:tb|тб)', lower)
    if tb_match:
        return int(tb_match.group(1)) * 1024

    gb_match = re.search(r'(\d+)\s*(?:gb|гб)', lower)
    if gb_match:
        return int(gb_match.group(1))

    return None
