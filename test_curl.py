import asyncio
import re
import json
import html
from curl_cffi.requests import AsyncSession

PROXY = "http://cmdkdzgdyfbkpzc226887-country-RU-package-mobile:uzoiutnqjy@eum.proxydoe.com:8000"


async def test():
    s = AsyncSession(
        impersonate="chrome136",
        proxies={"http": PROXY, "https": PROXY},
        timeout=30,
    )

    await s.get("https://m.avito.ru/", headers={"Accept-Language": "ru-RU,ru;q=0.9"})
    await asyncio.sleep(2)

    print("=== Загрузка страницы ===")
    r = await s.get(
        "https://www.avito.ru/all?q=iphone+15",
        headers={
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "ru-RU,ru;q=0.9",
        },
    )
    print(f"Status: {r.status_code}, Length: {len(r.text)}")
    page = r.text

    # 1. Извлекаем window.__preloadedState__
    print("\n=== window.__preloadedState__ ===")
    match = re.search(r'window\.__preloadedState__\s*=\s*({.+?});\s*</script>', page, re.DOTALL)
    if match:
        try:
            state = json.loads(match.group(1))
            print(f"Keys: {list(state.keys())[:20]}")
            # Рекурсивно ищем items/listings
            state_str = json.dumps(state)
            if "items" in state_str.lower():
                print("Contains 'items'!")
            with open("/root/avto-parser/debug_preloaded.json", "w") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            print("Saved to debug_preloaded.json")
        except json.JSONDecodeError as e:
            print(f"JSON parse error: {e}")
            raw = match.group(1)[:500]
            print(f"Raw: {raw}")
    else:
        print("Not found as plain JSON, trying encoded...")
        match2 = re.search(r'window\.__preloadedState__\s*=\s*"(.+?)";\s*</script>', page, re.DOTALL)
        if match2:
            raw = match2.group(1)[:200]
            print(f"Found encoded: {raw}...")
        else:
            print("Not found at all")

    # 2. Извлекаем __staticRouterHydrationData
    print("\n=== __staticRouterHydrationData ===")
    match = re.search(r'__staticRouterHydrationData\s*=\s*JSON\.parse\("(.+?)"\);\s*</script>', page, re.DOTALL)
    if match:
        raw = match.group(1)
        # Unescape JSON string
        try:
            unescaped = raw.replace('\\"', '"').replace('\\\\', '\\')
            data = json.loads(unescaped)
            print(f"Keys: {list(data.keys())[:10]}")
            with open("/root/avto-parser/debug_router.json", "w") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print("Saved to debug_router.json")
        except json.JSONDecodeError as e:
            print(f"Parse error: {e}")
            print(f"First 300 chars: {raw[:300]}")

    # 3. Извлекаем большой HTML-encoded JSON блок
    print("\n=== HTML-encoded JSON блоки ===")
    # Ищем блоки с &quot; которые содержат state/data
    for match in re.finditer(r'>(\{&quot;.{500,}?})</', page):
        encoded = match.group(1)
        decoded = html.unescape(encoded)
        try:
            data = json.loads(decoded)
            keys = list(data.keys())[:10]
            print(f"Found JSON block ({len(decoded)} chars), keys: {keys}")

            # Ищем items внутри
            data_str = json.dumps(data)
            for keyword in ["items", "catalog", "listing", "advert", "offer"]:
                count = data_str.lower().count(f'"{keyword}')
                if count > 0:
                    print(f"  Contains '{keyword}': {count} times")

            with open("/root/avto-parser/debug_encoded.json", "w") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print("  Saved to debug_encoded.json")
        except json.JSONDecodeError:
            print(f"Failed to parse block ({len(decoded)} chars)")
            print(f"  Start: {decoded[:200]}")

    # 4. Ищем все крупные JSON-подобные структуры
    print("\n=== Все JSON в <script> тегах ===")
    for match in re.finditer(r'<script[^>]*>(.*?)</script>', page, re.DOTALL):
        content = match.group(1).strip()
        if len(content) > 10000:
            # Пробуем декодировать HTML entities
            decoded = html.unescape(content)
            print(f"\nLarge script block: {len(decoded)} chars")
            print(f"  Start: {decoded[:300]}...")

            # Пробуем найти JSON внутри
            json_match = re.search(r'({["\w].{100,}})', decoded)
            if json_match:
                try:
                    obj = json.loads(json_match.group(1))
                    print(f"  Parsed JSON! Keys: {list(obj.keys())[:10]}")
                except json.JSONDecodeError:
                    pass

    s.close()


asyncio.run(test())
