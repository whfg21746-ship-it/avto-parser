"""Diagnostic test for Avito web-scraping.

Run on VPS:
  python test_curl.py                         # curl_cffi only (no ft cookie)
  python test_curl.py --playwright            # get ft cookie via Playwright first
  TEST_PROXY="" python test_curl.py           # without proxy
"""
import argparse
import asyncio
import html as html_lib
import json
import os
import random
import sys

from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession
from dotenv import load_dotenv

load_dotenv()

PROXY = os.getenv(
    "TEST_PROXY",
    "http://cmdkdzgdyfbkpzc226887-country-RU-package-mobile:uzoiutnqjy@eum.proxydoe.com:8000",
)

TEST_URLS = [
    "https://www.avito.ru/all/telefony",
    "https://www.avito.ru/moskva/telefony",
    "https://www.avito.ru/all?q=iphone+15",
    "https://www.avito.ru/all/telefony?q=iphone+15",
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


# ------------------------------------------------------------------
# Playwright cookie acquisition (like Duff89/parser_avito)
# ------------------------------------------------------------------

async def get_cookies_playwright() -> dict:
    """Use Playwright to get Avito cookies including the 'ft' fingerprint.

    Duff89/parser_avito visits a random non-existent ad page and waits up to
    50 seconds for Avito's JavaScript fingerprinting to set the 'ft' cookie.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("ERROR: playwright not installed!")
        print("  pip install playwright playwright-stealth")
        print("  playwright install chromium")
        return {}

    try:
        from playwright_stealth import Stealth
        stealth = Stealth()
    except ImportError:
        stealth = None
        print("  WARNING: playwright-stealth not installed, using basic mode")

    print("\n=== Getting cookies via Playwright ===")

    proxy_config = None
    if PROXY:
        # Parse proxy URL for Playwright format
        from urllib.parse import urlparse
        parsed = urlparse(PROXY)
        proxy_config = {
            "server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}",
        }
        if parsed.username:
            proxy_config["username"] = parsed.username
        if parsed.password:
            proxy_config["password"] = parsed.password
        print(f"Playwright proxy: {parsed.hostname}:{parsed.port}")

    cookies = {}

    if stealth:
        pw_ctx = stealth.use_async(async_playwright())
    else:
        from playwright.async_api import async_playwright as apw
        pw_ctx = apw()

    async with pw_ctx as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )

        context = await browser.new_context(
            proxy=proxy_config,
            locale="ru-RU",
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
        )

        page = await context.new_page()

        # Add stealth scripts if playwright-stealth not available
        if not stealth:
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
                Object.defineProperty(navigator, 'vendor', { get: () => 'Google Inc.' });
                window.chrome = { runtime: {} };
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
                Object.defineProperty(navigator, 'languages', { get: () => ['ru-RU', 'ru'] });
            """)

        # Visit a random non-existent ad (like Duff89 does)
        random_id = str(random.randint(1111111111, 9999999999))
        target_url = f"https://www.avito.ru/{random_id}"
        print(f"Visiting: {target_url}")

        try:
            await page.goto(target_url, timeout=60000, wait_until="domcontentloaded")
        except Exception as e:
            print(f"Page load error (may be expected): {e}")

        # Poll for ft cookie (up to 50 seconds, like Duff89)
        for attempt in range(10):
            raw_cookie = await page.evaluate("() => document.cookie")
            cookie_dict = {}
            for pair in raw_cookie.split(";"):
                pair = pair.strip()
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    cookie_dict[k.strip()] = v.strip()

            if cookie_dict.get("ft"):
                print(f"Got ft cookie on attempt {attempt + 1}!")
                cookies = cookie_dict
                break

            print(f"  Attempt {attempt + 1}/10: no ft cookie yet, waiting 5s...")
            await asyncio.sleep(5)
        else:
            print("WARNING: ft cookie not obtained after 50 seconds")
            # Return whatever cookies we got anyway
            raw_cookie = await page.evaluate("() => document.cookie")
            for pair in raw_cookie.split(";"):
                pair = pair.strip()
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    cookies[k.strip()] = v.strip()

        await browser.close()

    print(f"Playwright cookies: {list(cookies.keys())}")
    if "ft" in cookies:
        print(f"  ft = {cookies['ft'][:50]}...")
    return cookies


# ------------------------------------------------------------------
# Main test
# ------------------------------------------------------------------

async def test(use_playwright: bool = False):
    proxies = {"http": PROXY, "https": PROXY} if PROXY else None
    print(f"Proxy: {PROXY or '(none)'}")
    print(f"Python: {sys.version}")
    print(f"Mode: {'Playwright + curl_cffi' if use_playwright else 'curl_cffi only'}")
    print()

    # Step 0: Get cookies via Playwright if requested
    pw_cookies = {}
    if use_playwright:
        pw_cookies = await get_cookies_playwright()
        if not pw_cookies:
            print("\nFailed to get Playwright cookies, continuing without them...")
        print()

    s = AsyncSession(impersonate="chrome136", proxies=proxies, timeout=30)

    # Inject Playwright cookies into curl_cffi session
    if pw_cookies:
        for name, value in pw_cookies.items():
            s.cookies.set(name, value, domain=".avito.ru")
        print(f"Injected {len(pw_cookies)} Playwright cookies into session")

    # Step 1: Warm up
    print("=" * 60)
    print("=== Step 1: Pre-warm (visit avito.ru main page) ===")
    print("=" * 60)
    try:
        r = await s.get(
            "https://www.avito.ru/",
            headers={"Accept": "text/html", "Accept-Language": "ru-RU,ru;q=0.9"},
        )
        print(f"Warmup status: {r.status_code}, size: {len(r.text)} bytes")

        # Show cookies we got
        cookies = dict(s.cookies)
        print(f"Session cookies: {list(cookies.keys())}")
        if "ft" in cookies:
            print(f"  ft cookie: {cookies['ft'][:50]}...")
        else:
            print("  WARNING: No 'ft' fingerprint cookie!")
            print("  (curl_cffi can't execute JS to generate ft)")
            print("  Use --playwright flag to get ft via headless browser")

    except Exception as e:
        print(f"Warmup FAILED: {e}")
        print("\nCheck proxy or run on a VPS with Russian IP.")
        await s.close()
        return

    await asyncio.sleep(2)

    # Step 2: Try each test URL
    total = len(TEST_URLS)
    for idx, url in enumerate(TEST_URLS, 1):
        print(f"\n{'=' * 60}")
        print(f"=== URL {idx}/{total}: {url} ===")
        print(f"{'=' * 60}")

        try:
            r = await s.get(
                url,
                headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8",
                    "Referer": "https://www.avito.ru/",
                },
            )
        except Exception as e:
            print(f"Request FAILED: {e}")
            await asyncio.sleep(3)
            continue

        print(f"HTTP status: {r.status_code}, size: {len(r.text)} bytes")
        if r.status_code != 200:
            print(f"ERROR body: {r.text[:300]}")
            await asyncio.sleep(3)
            continue

        # Check page title
        soup = BeautifulSoup(r.text, "html.parser")
        title_tag = soup.find("title")
        print(f"Page <title>: {title_tag.text.strip()[:80] if title_tag else '(none)'}")

        # Count script types
        script_types = {}
        for sc in soup.select("script"):
            st = sc.get("type", "(none)")
            script_types[st] = script_types.get(st, 0) + 1
        print(f"Script types: {script_types}")

        # Check for CAPTCHA / block signs
        captcha_signs = ["captcha", "firewall", "blocked", "access denied"]
        body_lower = r.text[:5000].lower()
        for sign in captcha_signs:
            if sign in body_lower:
                print(f"  WARNING: Found '{sign}' in page content!")

        # Extract raw JSON
        raw = extract_raw_json(r.text)
        if not raw:
            print("NO mime/invalid JSON found!")
            if "window.__initialData__" in r.text:
                print("  Found window.__initialData__ pattern!")
            await asyncio.sleep(3)
            continue

        print(f"\nRaw JSON top-level keys: {list(raw.keys())}")

        # Navigate into 'state' if present
        state = raw.get("state", raw)
        if "state" in raw:
            print(f"state keys: {list(state.keys())[:15]}")

        # Check isBot flag
        is_bot = state.get("isBot")
        if is_bot is not None:
            print(f"  isBot = {is_bot}")
            if is_bot:
                print("  *** DETECTED AS BOT! ***")

        # Check data.status
        data_section = state.get("data", {})
        if isinstance(data_section, dict):
            status = data_section.get("status", {})
            if isinstance(status, dict) and status.get("code"):
                code = status["code"]
                print(f"  data.status.code = {code}")
                if code == 404:
                    print("  *** Server returned 404 in embedded data ***")
            print(f"  data keys: {list(data_section.keys())[:15]}")

        # Deep search for items anywhere in the JSON tree
        all_found = deep_find_items(raw)
        if all_found:
            print(f"\nFOUND items at {len(all_found)} location(s):")
            for items, found_path in all_found:
                print(f"  Path: {found_path} ({len(items)} items)")
                for i, item in enumerate(items[:3]):
                    title = item.get("title", "?")
                    price_d = item.get("priceDetailed", {})
                    price = price_d.get("value", "?") if isinstance(price_d, dict) else "?"
                    item_id = item.get("id", "?")
                    url_path = item.get("urlPath", "")
                    print(f"    [{i+1}] id={item_id}: {title} — {price}")
                    if url_path:
                        print(f"         https://www.avito.ru{url_path}")

            # Try detail page
            best_items = all_found[0][0]
            first_path = best_items[0].get("urlPath", "")
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
                            "Referer": url,
                        },
                    )
                    print(f"Detail HTTP status: {r2.status_code}, size: {len(r2.text)} bytes")
                    if r2.status_code == 200:
                        raw2 = extract_raw_json(r2.text)
                        if raw2:
                            state2 = raw2.get("state", raw2)
                            print(f"Detail state keys: {list(state2.keys())[:15]}")
                            for try_path in ["buyerItem", "item", "data.item", "data"]:
                                obj = state2
                                for part in try_path.split("."):
                                    obj = obj.get(part, {}) if isinstance(obj, dict) else {}
                                if isinstance(obj, dict) and (obj.get("title") or obj.get("description")):
                                    print(f"\nItem data at '{try_path}':")
                                    print(f"  title: {obj.get('title', '?')}")
                                    desc = obj.get("description", "")
                                    print(f"  description: {desc[:120]}..." if desc else "  description: (none)")
                                    seller = obj.get("seller", {})
                                    if seller:
                                        print(f"  seller: {json.dumps(seller, ensure_ascii=False)[:200]}")
                                    break
                            else:
                                print("  Could not find item data in detail page JSON")
                except Exception as e:
                    print(f"Detail FAILED: {e}")

            break
        else:
            print("\nNo items found anywhere in JSON.")
            # Compact structure dump
            print("JSON structure dump:")
            def dump_structure(d, indent=0, max_depth=4):
                if indent > max_depth or not isinstance(d, dict):
                    return
                for k, v in list(d.items())[:20]:
                    prefix = "  " * indent
                    if isinstance(v, dict):
                        keys_preview = list(v.keys())[:8]
                        print(f"{prefix}{k}: dict({len(v)}) -> {keys_preview}")
                        dump_structure(v, indent + 1, max_depth)
                    elif isinstance(v, list):
                        sample = ""
                        if v:
                            first = v[0]
                            if isinstance(first, dict):
                                sample = f"keys={list(first.keys())[:5]}"
                            else:
                                sample = str(first)[:40]
                        print(f"{prefix}{k}: list[{len(v)}] {sample}")
                    elif isinstance(v, str) and len(v) > 80:
                        print(f"{prefix}{k}: str({len(v)} chars)")
                    else:
                        print(f"{prefix}{k}: {str(v)[:80]}")
            dump_structure(raw)

        await asyncio.sleep(3)

    print(f"\nFinal session cookies: {list(dict(s.cookies).keys())}")
    await s.close()
    print("\n=== Done ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--playwright", action="store_true",
                        help="Use Playwright to get ft cookie first")
    args = parser.parse_args()
    asyncio.run(test(use_playwright=args.playwright))
