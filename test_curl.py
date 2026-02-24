import asyncio
import re
from curl_cffi.requests import AsyncSession

PROXY = "http://cmdkdzgdyfbkpzc226887-country-RU-package-mobile:uzoiutnqjy@eum.proxydoe.com:8000"
OLD_KEY = "af0deccbgcgidddjgnvljitntccdduijhdinfgjgfjir"

PARAMS = {"query": "iphone 15", "locationId": 621540, "limit": 3, "sort": "date"}
JSON_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ru-RU,ru;q=0.9",
    "Referer": "https://www.avito.ru/all?q=iphone+15",
    "Origin": "https://www.avito.ru",
}


async def try_url(s, label, url, params=None, extra_headers=None):
    """Пробуем один endpoint."""
    headers = {**JSON_HEADERS}
    if extra_headers:
        headers.update(extra_headers)
    try:
        r = await s.get(url, params=params, headers=headers)
        body = r.text[:200]
        has_items = '"items"' in r.text or '"result"' in r.text
        tag = "HAS DATA!" if has_items and r.status_code == 200 else ""
        print(f"  {label}: {r.status_code} {tag} {body}")
        if has_items and r.status_code == 200:
            return True
    except Exception as e:
        print(f"  {label}: ERROR {str(e)[:80]}")
    return False


async def test():
    s = AsyncSession(
        impersonate="chrome136",
        proxies={"http": PROXY, "https": PROXY},
        timeout=30,
    )

    # Прогрев
    print("=== Прогрев ===")
    r = await s.get("https://www.avito.ru/", headers={"Accept-Language": "ru-RU,ru;q=0.9"})
    print(f"Warmup: {r.status_code}")
    await asyncio.sleep(3)

    # 1. Mobile API v11-v20 с ключом
    print("\n=== Mobile API с ключом (по одному, с паузами) ===")
    for ver in [11, 12, 13, 14, 15, 16, 17, 18, 19, 20]:
        url = f"https://m.avito.ru/api/{ver}/items"
        found = await try_url(s, f"m.avito api/{ver}+key", url, {**PARAMS, "key": OLD_KEY})
        if found:
            break
        await asyncio.sleep(4)

    await asyncio.sleep(5)

    # 2. Mobile API v11-v20 без ключа
    print("\n=== Mobile API без ключа ===")
    for ver in [11, 12, 13, 14]:
        url = f"https://m.avito.ru/api/{ver}/items"
        found = await try_url(s, f"m.avito api/{ver} nokey", url, PARAMS)
        if found:
            break
        await asyncio.sleep(4)

    await asyncio.sleep(5)

    # 3. Web API endpoints (www.avito.ru)
    print("\n=== Web API endpoints ===")
    web_endpoints = [
        "/web/1/items",
        "/web/2/items",
        "/web/1/catalog",
        "/web/1/search",
        "/api/1/items",
        "/api/9/items",
        "/api/search",
        "/graphql",
    ]
    for ep in web_endpoints:
        url = f"https://www.avito.ru{ep}"
        found = await try_url(s, f"www{ep}", url, PARAMS)
        if found:
            break
        await asyncio.sleep(3)

    await asyncio.sleep(3)

    # 4. Попробуем BFF-стиль запрос
    print("\n=== BFF / internal endpoints ===")
    bff_urls = [
        "https://www.avito.ru/web/1/catalog/items",
        "https://www.avito.ru/web/1/main/items",
        "https://www.avito.ru/web/2/catalog/items",
        "https://socket.avito.ru/api/search",
        "https://bff.avito.ru/api/1/items",
    ]
    for url in bff_urls:
        found = await try_url(s, url.split("//")[1][:50], url, PARAMS)
        if found:
            break
        await asyncio.sleep(3)

    # 5. Попробуем JS bundle для поиска endpoint
    print("\n=== Поиск endpoint в JS бандлах ===")
    r = await s.get("https://www.avito.ru/all?q=iphone",
                     headers={"Accept": "text/html", "Accept-Language": "ru-RU,ru;q=0.9"})
    js_urls = re.findall(r'src="(https?://[^"]*\.js[^"]*)"', r.text)
    print(f"Found {len(js_urls)} JS files")
    # Берём самый большой (main bundle)
    for js_url in js_urls[:3]:
        print(f"\n  Checking: {js_url[-60:]}")
        try:
            jr = await s.get(js_url)
            js_code = jr.text
            # Ищем API endpoints
            apis = set()
            for m in re.finditer(r'["\'](/api/\d+/\w+)["\']', js_code):
                apis.add(m.group(1))
            for m in re.finditer(r'["\'](/web/\d+/\w+)["\']', js_code):
                apis.add(m.group(1))
            for m in re.finditer(r'["\']([^"\']*items[^"\']*api[^"\']*)["\']', js_code):
                if len(m.group(1)) < 80:
                    apis.add(m.group(1))
            if apis:
                print(f"    APIs found: {sorted(apis)}")
        except Exception as e:
            print(f"    Error: {str(e)[:60]}")
        await asyncio.sleep(2)

    s.close()


asyncio.run(test())
