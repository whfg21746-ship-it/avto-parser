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
import re

from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession
from dotenv import load_dotenv

load_dotenv()

PROXY = os.getenv(
    "TEST_PROXY",
    "http://cmdkdzgdyfbkpzc226887-country-RU-package-mobile:uzoiutnqjy@eum.proxydoe.com:8000",
)

# Multiple test URLs — try simple ones first
TEST_URLS = [
    "https://www.avito.ru/all/telefony?q=iphone+15",
    "https://www.avito.ru/all?q=iphone+15",
    "https://www.avito.ru/moskva/telefony?q=iphone",
    "https://www.avito.ru/all/telefony/mobilnye_telefony/apple-ASgBAgICA0SywA2I_Dc?cd=1&s=104",
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


def deep_find_items(data: dict, path: str = "") -> tuple[list[dict], str]:
    """Recursively search for 'items' list inside nested dict."""
    if not isinstance(data, dict):
        return [], path

    # Direct check
    items = data.get("items")
    if isinstance(items, list) and len(items) > 0 and isinstance(items[0], dict):
        if items[0].get("id") or items[0].get("title"):
            return items, f"{path}.items"

    # Check catalog.items
    catalog = data.get("catalog")
    if isinstance(catalog, dict):
        items = catalog.get("items")
        if isinstance(items, list) and len(items) > 0:
            return items, f"{path}.catalog.items"

    # Recurse into dict values (max 3 levels)
    if path.count(".") < 4:
        for key, val in data.items():
            if isinstance(val, dict):
                found, found_path = deep_find_items(val, f"{path}.{key}")
                if found:
                    return found, found_path

    return [], path


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
        print("\nCheck proxy or run on a VPS with Russian IP.")
        await s.close()
        return
    await asyncio.sleep(2)

    # Step 2: Try each test URL
    for url in TEST_URLS:
        print(f"\n{'='*60}")
        print(f"=== Testing: {url} ===")
        print(f"{'='*60}")

        try:
            r = await s.get(
                url,
                headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8",
                },
            )
        except Exception as e:
            print(f"Request FAILED: {e}")
            continue

        print(f"Status: {r.status_code}, Size: {len(r.text)} bytes")
        if r.status_code != 200:
            print(f"ERROR: {r.text[:200]}")
            continue

        # Count script types
        soup = BeautifulSoup(r.text, "html.parser")
        script_types = {}
        for sc in soup.select("script"):
            st = sc.get("type", "(none)")
            script_types[st] = script_types.get(st, 0) + 1
        print(f"Script types: {script_types}")

        # Extract raw JSON (don't unwrap yet)
        raw = extract_raw_json(r.text)
        if not raw:
            print("NO mime/invalid JSON found!")
            continue

        print(f"Raw top-level keys: {list(raw.keys())}")

        # Check for data.status
        data_section = raw.get("data", {})
        if isinstance(data_section, dict):
            status = data_section.get("status", {})
            if isinstance(status, dict) and status.get("code"):
                print(f"data.status = {status}")

        # Deep search for items in entire JSON tree
        items, found_path = deep_find_items(raw)
        if items:
            print(f"\nFOUND {len(items)} items at path: {found_path}")
            print("\n--- First 3 items ---")
            for i, item in enumerate(items[:3]):
                title = item.get("title", "?")
                price_d = item.get("priceDetailed", {})
                price = price_d.get("value", "?") if isinstance(price_d, dict) else "?"
                url_path = item.get("urlPath", "")
                loc = item.get("location", {})
                city = loc.get("name", "?") if isinstance(loc, dict) else "?"
                item_id = item.get("id", "?")
                print(f"  [{i+1}] {title}")
                print(f"      Price: {price}, City: {city}, ID: {item_id}")
                if url_path:
                    print(f"      URL: https://www.avito.ru{url_path}")

            # Test detail page for first item
            first_path = items[0].get("urlPath", "")
            if first_path:
                detail_url = f"https://www.avito.ru{first_path}"
                print(f"\n=== Fetching detail page ===\n{detail_url}")
                await asyncio.sleep(3)
                try:
                    r2 = await s.get(
                        detail_url,
                        headers={
                            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                            "Accept-Language": "ru-RU,ru;q=0.9",
                        },
                    )
                    print(f"Detail status: {r2.status_code}, Size: {len(r2.text)} bytes")
                    if r2.status_code == 200:
                        raw2 = extract_raw_json(r2.text)
                        if raw2:
                            print(f"Detail raw keys: {list(raw2.keys())}")
                            # Look for item data in various paths
                            for try_path in ["item", "data.item", "data"]:
                                obj = raw2
                                for part in try_path.split("."):
                                    obj = obj.get(part, {}) if isinstance(obj, dict) else {}
                                if isinstance(obj, dict) and (obj.get("title") or obj.get("description")):
                                    print(f"\nItem data at '{try_path}':")
                                    print(f"  title: {obj.get('title', '?')}")
                                    desc = obj.get("description", "")
                                    print(f"  description: {desc[:100]}..." if desc else "  description: (none)")
                                    seller = obj.get("seller", {})
                                    if seller:
                                        print(f"  seller: {json.dumps(seller, ensure_ascii=False)[:200]}")
                                    params = obj.get("params", [])
                                    if params:
                                        print(f"  params: {json.dumps(params[:3], ensure_ascii=False)[:200]}")
                                    break
                            else:
                                # Dump second-level keys for debugging
                                for k, v in raw2.items():
                                    if isinstance(v, dict):
                                        print(f"  {k}: keys={list(v.keys())[:10]}")
                                    else:
                                        print(f"  {k}: {str(v)[:80]}")
                except Exception as e:
                    print(f"Detail FAILED: {e}")

            # Success — no need to try more URLs
            break
        else:
            print("\nNo items found. Dumping nested structure:")
            def dump_structure(d, indent=0, max_depth=3):
                if indent > max_depth or not isinstance(d, dict):
                    return
                for k, v in d.items():
                    if isinstance(v, dict):
                        keys_preview = list(v.keys())[:8]
                        print(f"{'  '*indent}{k}: dict({len(v)} keys) -> {keys_preview}")
                        dump_structure(v, indent+1, max_depth)
                    elif isinstance(v, list):
                        sample = str(v[0])[:60] if v else "(empty)"
                        print(f"{'  '*indent}{k}: list[{len(v)}] first={sample}")
                    else:
                        print(f"{'  '*indent}{k}: {str(v)[:80]}")
            dump_structure(raw)

        await asyncio.sleep(3)

    await s.close()
    print("\n=== Done ===")


asyncio.run(test())
