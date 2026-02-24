"""Quick smoke-test for the new web-scraping approach.

Run:  python test_curl.py
"""
import asyncio
import html as html_lib
import json
import os

from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession
from dotenv import load_dotenv

load_dotenv()

PROXY = os.getenv(
    "TEST_PROXY",
    "http://cmdkdzgdyfbkpzc226887-country-RU-package-mobile:uzoiutnqjy@eum.proxydoe.com:8000",
)

# Test URL — Apple phones, sorted by date
TEST_URL = "https://www.avito.ru/all/telefony/mobilnye_telefony/apple-ASgBAgICA0SywA2I_Dc?cd=1&s=104"


def extract_json_from_html(html_text: str) -> dict:
    """Extract JSON from <script type="mime/invalid"> tags."""
    soup = BeautifulSoup(html_text, "html.parser")
    for script in soup.select("script"):
        if script.get("type") != "mime/invalid":
            continue
        try:
            content = html_lib.unescape(script.text)
            data = json.loads(content)
            if "state" in data:
                return data["state"]
            if "data" in data:
                return data["data"]
            return data
        except Exception as e:
            print(f"  JSON parse error: {e}")
    return {}


def find_items(data: dict) -> list[dict]:
    """Find catalog items in extracted JSON."""
    catalog = data.get("catalog", {})
    if isinstance(catalog, dict) and catalog.get("items"):
        return catalog["items"]
    inner = data.get("data", {})
    if isinstance(inner, dict):
        catalog = inner.get("catalog", {})
        if isinstance(catalog, dict) and catalog.get("items"):
            return catalog["items"]
    return data.get("items", [])


async def test():
    proxies = {"http": PROXY, "https": PROXY} if PROXY else None
    s = AsyncSession(impersonate="chrome136", proxies=proxies, timeout=30)

    # Step 1: Warm up
    print("=== Pre-warm ===")
    r = await s.get(
        "https://www.avito.ru/",
        headers={"Accept": "text/html", "Accept-Language": "ru-RU,ru;q=0.9"},
    )
    print(f"Warmup: {r.status_code}")
    await asyncio.sleep(2)

    # Step 2: Fetch search page
    print(f"\n=== Fetch search page ===\n{TEST_URL}")
    r = await s.get(
        TEST_URL,
        headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8",
        },
    )
    print(f"Status: {r.status_code}, Size: {len(r.text)} bytes")

    if r.status_code != 200:
        print(f"ERROR: {r.text[:300]}")
        s.close()
        return

    # Step 3: Extract JSON
    print("\n=== Extract embedded JSON ===")
    data = extract_json_from_html(r.text)
    print(f"Top-level keys: {list(data.keys())[:15]}")

    items = find_items(data)
    print(f"Found {len(items)} items in catalog")

    if items:
        print("\n=== First 3 items ===")
        for i, item in enumerate(items[:3]):
            title = item.get("title", "?")
            price_d = item.get("priceDetailed", {})
            price = price_d.get("value", "?") if isinstance(price_d, dict) else "?"
            url_path = item.get("urlPath", "")
            loc = item.get("location", {})
            city = loc.get("name", "?") if isinstance(loc, dict) else "?"
            item_id = item.get("id", "?")
            print(f"\n  [{i+1}] {title}")
            print(f"      Price: {price}")
            print(f"      City: {city}")
            print(f"      ID: {item_id}")
            print(f"      URL: https://www.avito.ru{url_path}")

        # Step 4: Test item details
        first = items[0]
        url_path = first.get("urlPath", "")
        if url_path:
            detail_url = f"https://www.avito.ru{url_path}"
            print(f"\n=== Fetch item details ===\n{detail_url}")
            await asyncio.sleep(3)
            r2 = await s.get(
                detail_url,
                headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "ru-RU,ru;q=0.9",
                },
            )
            print(f"Status: {r2.status_code}, Size: {len(r2.text)} bytes")
            if r2.status_code == 200:
                detail_data = extract_json_from_html(r2.text)
                print(f"Detail top-level keys: {list(detail_data.keys())[:15]}")
                # Try to find description
                desc = detail_data.get("description", "")
                if not desc:
                    item_sub = detail_data.get("item", {})
                    desc = item_sub.get("description", "") if isinstance(item_sub, dict) else ""
                seller = detail_data.get("seller", {})
                print(f"Description: {desc[:120]}..." if desc else "Description: (not found)")
                print(f"Seller data: {seller}" if seller else "Seller: (not found in top level)")
    else:
        print("\nNo items found! Dumping data structure for debugging:")
        for key, val in data.items():
            val_str = str(val)[:100]
            print(f"  {key}: {val_str}")

    s.close()
    print("\n=== Done ===")


asyncio.run(test())
