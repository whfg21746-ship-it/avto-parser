import asyncio
import re
from curl_cffi.requests import AsyncSession

PROXY = "http://cmdkdzgdyfbkpzc226887-country-RU-package-mobile:uzoiutnqjy@eum.proxydoe.com:8000"
OLD_KEY = "af0deccbgcgidddjgnvljitntccdduijhdinfgjgfjir"


async def test():
    s = AsyncSession(
        impersonate="chrome136",
        proxies={"http": PROXY, "https": PROXY},
        timeout=30,
    )

    headers = {
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8",
    }

    # Прогрев
    print("=== Прогрев ===")
    r = await s.get("https://m.avito.ru/", headers=headers)
    print(f"Warmup: {r.status_code}")
    await asyncio.sleep(3)

    # Тест 1: api/9 без ключа
    print("\n=== api/9 без ключа ===")
    r = await s.get(
        "https://m.avito.ru/api/9/items",
        params={"query": "iphone 15", "locationId": 621540, "limit": 3},
        headers={"Accept": "application/json", "Referer": "https://m.avito.ru/"},
    )
    print(f"Status: {r.status_code}")
    print(f"Body: {r.text[:300]}")
    await asyncio.sleep(5)

    # Тест 2: api/10 без ключа
    print("\n=== api/10 без ключа ===")
    r = await s.get(
        "https://m.avito.ru/api/10/items",
        params={"query": "iphone 15", "locationId": 621540, "limit": 3},
        headers={"Accept": "application/json", "Referer": "https://m.avito.ru/"},
    )
    print(f"Status: {r.status_code}")
    print(f"Body: {r.text[:300]}")
    await asyncio.sleep(5)

    # Тест 3: веб-поиск m.avito.ru
    print("\n=== Веб-поиск m.avito.ru ===")
    r = await s.get(
        "https://m.avito.ru/all?q=iphone+15",
        headers={"Accept": "text/html", **headers},
    )
    print(f"Status: {r.status_code}")
    for pattern in ["__initialData__", "__NEXT_DATA__", "catalog-serp", "iva-item", "items"]:
        if pattern in r.text:
            print(f"  Found: {pattern}")
    print(f"Page length: {len(r.text)} chars")
    await asyncio.sleep(5)

    # Тест 4: десктоп www.avito.ru
    print("\n=== Веб-поиск www.avito.ru ===")
    r = await s.get(
        "https://www.avito.ru/all?q=iphone+15",
        headers={"Accept": "text/html", **headers},
    )
    print(f"Status: {r.status_code}")
    for pattern in ["__initialData__", "__NEXT_DATA__", "catalog-serp", "iva-item", "items"]:
        if pattern in r.text:
            print(f"  Found: {pattern}")
    print(f"Page length: {len(r.text)} chars")

    s.close()


asyncio.run(test())
