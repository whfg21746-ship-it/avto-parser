"""Quick smoke-test for the new web-scraping approach.

Run on VPS:
  python test_curl.py
  TEST_PROXY="" python test_curl.py          # without proxy
  TEST_PROXY="http://user:pass@host:port" python test_curl.py
"""
import asyncio
import html as html_lib
import json
import os
import sys

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
    print(f"Proxy: {PROXY or '(none)'}\n")

    s = AsyncSession(impersonate="chrome136", proxies=proxies, timeout=30)

    # Step 1: Warm up
    print("=== Pre-warm ===")
    try:
        r = await s.get(
            "https://www.avito.ru/",
            headers={"Accept": "text/html", "Accept-Language": "ru-RU,ru;q=0.9"},
        )
        print(f"Warmup: {r.status_code}")
    except Exception as e:
        print(f"Warmup FAILED: {e}")
        print("\nНе удалось подключиться к avito.ru.")
        print("Проверь прокси или запусти на VPS с российским IP.")
        s.close()
        return
    await asyncio.sleep(2)

    # Step 2: Fetch search page
    print(f"\n=== Fetch search page ===\n{TEST_URL}")
    try:
        r = await s.get(
            TEST_URL,
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8",
            },
        )
    except Exception as e:
        print(f"Search FAILED: {e}")
        s.close()
        return

    print(f"Status: {r.status_code}, Size: {len(r.text)} bytes")

    if r.status_code != 200:
        print(f"ERROR: {r.text[:300]}")
        s.close()
        return

    # Step 3: Count script types for debugging
    soup_debug = BeautifulSoup(r.text, "html.parser")
    script_types = {}
    for sc in soup_debug.select("script"):
        st = sc.get("type", "(none)")
        script_types[st] = script_types.get(st, 0) + 1
    print(f"\nScript tags by type: {script_types}")

    # Step 4: Extract JSON
    print("\n=== Extract embedded JSON ===")
    data = extract_json_from_html(r.text)
    if data:
        print(f"Top-level keys: {list(data.keys())[:20]}")
    else:
        print("NO mime/invalid JSON found!")
        print("\nFallback: checking __initialData__ ...")
        import re
        for pat in [r'window\.__initialData__\s*=\s*"(.+?)"', r'window\.__initialData__\s*=\s*(\{.+?\})\s*;']:
            m = re.search(pat, r.text, re.DOTALL)
            if m:
                print(f"  Found __initialData__ match ({len(m.group(1))} chars)")
                break
        else:
            print("  No __initialData__ either.")
        print("\nDumping first 2000 chars of HTML for debugging:")
        print(r.text[:2000])
        s.close()
        return

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

        # Step 5: Test item details
        first = items[0]
        url_path = first.get("urlPath", "")
        if url_path:
            detail_url = f"https://www.avito.ru{url_path}"
            print(f"\n=== Fetch item details ===\n{detail_url}")
            await asyncio.sleep(3)
            try:
                r2 = await s.get(
                    detail_url,
                    headers={
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "Accept-Language": "ru-RU,ru;q=0.9",
                    },
                )
            except Exception as e:
                print(f"Detail fetch FAILED: {e}")
                s.close()
                return

            print(f"Status: {r2.status_code}, Size: {len(r2.text)} bytes")
            if r2.status_code == 200:
                detail_data = extract_json_from_html(r2.text)
                if detail_data:
                    print(f"Detail top-level keys: {list(detail_data.keys())[:20]}")
                    # Try to find description
                    desc = detail_data.get("description", "")
                    if not desc:
                        item_sub = detail_data.get("item", {})
                        desc = item_sub.get("description", "") if isinstance(item_sub, dict) else ""
                    seller = detail_data.get("seller", {})
                    print(f"Description: {desc[:120]}..." if desc else "Description: (not found)")
                    if seller:
                        print(f"Seller: {json.dumps(seller, ensure_ascii=False)[:200]}")
                    else:
                        print("Seller: (not found in top level)")
                else:
                    print("NO mime/invalid JSON on detail page!")
                    # Debug: dump script types
                    soup2 = BeautifulSoup(r2.text, "html.parser")
                    st2 = {}
                    for sc in soup2.select("script"):
                        t = sc.get("type", "(none)")
                        st2[t] = st2.get(t, 0) + 1
                    print(f"Script types on detail page: {st2}")
    else:
        print("\nNo items found! Dumping data structure for debugging:")
        for key, val in data.items():
            val_str = str(val)[:150]
            print(f"  {key}: {val_str}")

    s.close()
    print("\n=== Done ===")


asyncio.run(test())
