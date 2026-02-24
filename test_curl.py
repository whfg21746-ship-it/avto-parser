"""Diagnostic test for Avito web-scraping with embedded redirect following.

Run on VPS:
  python test_curl.py
  TEST_PROXY="" python test_curl.py           # without proxy
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

BASE = "https://www.avito.ru"

TEST_URLS = [
    f"{BASE}/all/telefony?q=iphone+15",
    f"{BASE}/all?q=macbook+air",
    f"{BASE}/all/telefony",
]


def extract_raw_json(html_text: str) -> dict:
    """Extract the RAW top-level JSON from <script type="mime/invalid">."""
    soup = BeautifulSoup(html_text, "html.parser")
    for script in soup.select("script"):
        if script.get("type") != "mime/invalid":
            continue
        try:
            content = html_lib.unescape(script.text)
            return json.loads(content)
        except Exception as e:
            print(f"  JSON parse error: {e}")
    return {}


def get_state(raw: dict) -> dict:
    """Get the state dict from raw JSON."""
    return raw.get("state", raw)


def get_embedded_redirect(state: dict) -> str | None:
    """Check if embedded JSON contains a suspense redirect (301/302)."""
    redirect = state.get("redirect")
    if redirect and isinstance(redirect, str) and redirect.startswith("/"):
        return redirect

    inner = state.get("data", {})
    if isinstance(inner, dict):
        status = inner.get("status", {})
        if isinstance(status, dict) and status.get("code") in (301, 302):
            return inner.get("url")

    return None


def find_catalog_items(state: dict) -> list[dict]:
    """Find catalog items in state.data.catalog.items."""
    data = state.get("data", {})
    if not isinstance(data, dict):
        return []

    catalog = data.get("catalog", {})
    if isinstance(catalog, dict):
        items = catalog.get("items")
        if isinstance(items, list):
            return items

    return []


def deep_find_items(data, path="", depth=0):
    """Recursively search for any 'items' list that looks like catalog items."""
    results = []
    if depth > 5 or not isinstance(data, dict):
        return results

    items = data.get("items")
    if isinstance(items, list) and len(items) > 0 and isinstance(items[0], dict):
        first = items[0]
        if first.get("id") or first.get("title") or first.get("urlPath"):
            results.append((items, f"{path}.items"))

    for key, val in data.items():
        if key == "items":
            continue
        if isinstance(val, dict):
            results.extend(deep_find_items(val, f"{path}.{key}", depth + 1))

    return results


async def fetch_page(s, url):
    """Fetch a page and return (response, html_text) or (None, None)."""
    try:
        r = await s.get(
            url,
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8",
                "Referer": f"{BASE}/",
            },
        )
        return r, r.text if r.status_code == 200 else None
    except Exception as e:
        print(f"Request FAILED: {e}")
        return None, None


async def test():
    proxies = {"http": PROXY, "https": PROXY} if PROXY else None
    print(f"Proxy: {PROXY or '(none)'}")
    print(f"Python: {sys.version}\n")

    s = AsyncSession(impersonate="chrome136", proxies=proxies, timeout=30)

    # Step 1: Warm up
    print("=" * 60)
    print("=== Step 1: Pre-warm ===")
    print("=" * 60)
    try:
        r = await s.get(
            f"{BASE}/",
            headers={"Accept": "text/html", "Accept-Language": "ru-RU,ru;q=0.9"},
        )
        print(f"Warmup: {r.status_code}, {len(r.text)} bytes")
    except Exception as e:
        print(f"Warmup FAILED: {e}")
        await s.close()
        return

    await asyncio.sleep(2)

    # Step 2: Try each test URL (follow embedded redirects)
    total = len(TEST_URLS)
    for idx, url in enumerate(TEST_URLS, 1):
        print(f"\n{'=' * 60}")
        print(f"=== URL {idx}/{total}: {url} ===")
        print(f"{'=' * 60}")

        current_url = url
        items = []

        # Follow up to 3 embedded redirects
        for redirect_num in range(4):
            r, html_text = await fetch_page(s, current_url)
            if not html_text:
                if r:
                    print(f"HTTP {r.status_code}: {r.text[:200]}")
                break

            print(f"HTTP 200, {len(html_text)} bytes")

            raw = extract_raw_json(html_text)
            if not raw:
                print("NO mime/invalid JSON found!")
                break

            state = get_state(raw)

            # Check for embedded redirect
            redirect = get_embedded_redirect(state)
            if redirect:
                redirect_url = f"{BASE}{redirect}" if redirect.startswith("/") else redirect
                print(f"  -> Embedded 301 redirect to: {redirect}")
                current_url = redirect_url
                await asyncio.sleep(1)
                continue

            # Check isBot
            is_bot = state.get("isBot")
            if is_bot:
                print("  WARNING: isBot = True")

            # Check data.status
            data_section = state.get("data", {})
            if isinstance(data_section, dict):
                status = data_section.get("status", {})
                if isinstance(status, dict) and status.get("code"):
                    code = status["code"]
                    if code not in (200,):
                        print(f"  data.status.code = {code}")

            # Try to find items
            items = find_catalog_items(state)
            if not items:
                # Deep search as fallback
                all_found = deep_find_items(raw)
                if all_found:
                    items = all_found[0][0]
                    print(f"  Found items via deep search at: {all_found[0][1]}")

            if items:
                break
            else:
                print("  No items found on this page")
                # Show data keys for debugging
                if isinstance(data_section, dict):
                    print(f"  data keys: {list(data_section.keys())[:10]}")
                break

        if not items:
            print("  FAILED: no items after following redirects")
            await asyncio.sleep(2)
            continue

        # Show results
        print(f"\nFOUND {len(items)} items!")
        print(f"Final URL: {current_url}")
        print("\n--- First 5 items ---")
        for i, item in enumerate(items[:5]):
            title = item.get("title", "?")
            price_d = item.get("priceDetailed", {})
            price = price_d.get("value", "?") if isinstance(price_d, dict) else "?"
            item_id = item.get("id", "?")
            url_path = item.get("urlPath", "")
            loc = item.get("location", {})
            city = loc.get("name", "?") if isinstance(loc, dict) else "?"
            print(f"  [{i+1}] {title}")
            print(f"      Price: {price}, City: {city}, ID: {item_id}")
            if url_path:
                print(f"      URL: {BASE}{url_path}")

        # Try detail page for first item
        first_path = items[0].get("urlPath", "")
        if first_path:
            detail_url = f"{BASE}{first_path}"
            print(f"\n=== Detail page: {detail_url} ===")
            await asyncio.sleep(3)
            r2, html2 = await fetch_page(s, detail_url)
            if html2:
                print(f"HTTP 200, {len(html2)} bytes")
                raw2 = extract_raw_json(html2)
                if raw2:
                    state2 = get_state(raw2)

                    # Follow redirect on detail page too
                    redirect2 = get_embedded_redirect(state2)
                    if redirect2:
                        print(f"  -> Detail redirect to: {redirect2}")
                        await asyncio.sleep(1)
                        r3, html3 = await fetch_page(s, f"{BASE}{redirect2}")
                        if html3:
                            raw2 = extract_raw_json(html3)
                            state2 = get_state(raw2) if raw2 else {}

                    # Look for item data in known paths
                    for try_path in ["buyerItem", "item", "data.buyerItem", "data.item", "data"]:
                        obj = state2
                        for part in try_path.split("."):
                            obj = obj.get(part, {}) if isinstance(obj, dict) else {}
                        if isinstance(obj, dict) and (obj.get("title") or obj.get("description")):
                            print(f"\nItem data at '{try_path}':")
                            print(f"  title: {obj.get('title', '?')}")
                            desc = obj.get("description", "")
                            print(f"  description: {desc[:150]}..." if len(desc) > 150 else f"  description: {desc or '(none)'}")
                            price = obj.get("price") or obj.get("priceDetailed", {})
                            print(f"  price: {price}")
                            seller = obj.get("seller", {})
                            if isinstance(seller, dict):
                                print(f"  seller: items={seller.get('itemsCount', '?')}, closed={seller.get('closedItemsCount', '?')}")
                            params = obj.get("params", [])
                            if params and isinstance(params, list):
                                print(f"  params ({len(params)}): {json.dumps(params[:3], ensure_ascii=False)[:300]}")
                            break
                    else:
                        print("  Could not find item data")
                        print(f"  state keys: {list(state2.keys())[:15]}")
                else:
                    print("  No JSON in detail page")
            else:
                print(f"  Detail page failed")

        # Success
        break

    await s.close()
    print("\n=== Done ===")


asyncio.run(test())
