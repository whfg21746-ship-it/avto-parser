import asyncio
import re
import json
from urllib.parse import unquote
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

    # 1. Ищем data-marker атрибуты (Avito использует их)
    print("\n=== data-marker атрибуты ===")
    markers = re.findall(r'data-marker="([^"]+)"', page)
    unique_markers = sorted(set(markers))
    print(f"Found {len(markers)} total, {len(unique_markers)} unique:")
    for m in unique_markers[:30]:
        count = markers.count(m)
        print(f"  {m}: {count}")

    # 2. Ищем ссылки на объявления
    print("\n=== Ссылки на объявления ===")
    ad_links = re.findall(r'href="(/[^"]*?)"\s[^>]*data-marker="item-title"', page)
    if not ad_links:
        ad_links = re.findall(r'data-marker="item-title"[^>]*href="(/[^"]*?)"', page)
    if not ad_links:
        # Более общий паттерн — ссылки с ID объявления
        ad_links = re.findall(r'href="(/[\w/-]+_(\d{8,}))"', page)
    print(f"Found {len(ad_links)} ad links:")
    for link in ad_links[:5]:
        print(f"  {link}")

    # 3. Ищем item контейнеры
    print("\n=== Item контейнеры ===")
    item_divs = re.findall(r'data-marker="item\b([^"]*)"', page)
    print(f"data-marker='item*': {len(item_divs)} matches")
    for m in set(item_divs)[:10]:
        print(f"  item{m}: {item_divs.count(m)}")

    # 4. Ищем itemId / data-item-id
    print("\n=== Item IDs ===")
    item_ids = re.findall(r'data-item-id="(\d+)"', page)
    if not item_ids:
        item_ids = re.findall(r'data-id="(\d+)"', page)
    if not item_ids:
        item_ids = re.findall(r'"itemId"\s*:\s*"?(\d+)"?', page)
    print(f"Found {len(item_ids)} item IDs:")
    for iid in item_ids[:5]:
        print(f"  {iid}")

    # 5. Ищем цены в HTML
    print("\n=== Цены в HTML ===")
    # Avito часто использует meta content для цен
    prices_meta = re.findall(r'content="(\d[\d\s]*)"[^>]*itemprop="price"', page)
    if not prices_meta:
        prices_meta = re.findall(r'itemprop="price"[^>]*content="(\d[\d\s]*)"', page)
    # Также ищем в тексте
    prices_text = re.findall(r'>(\d{1,3}(?:\s\d{3})*)\s*₽<', page)
    if not prices_text:
        prices_text = re.findall(r'(\d{1,3}(?:[\s\xa0]\d{3})+)\s*₽', page)
    print(f"Meta prices: {prices_meta[:5]}")
    print(f"Text prices: {prices_text[:5]}")

    # 6. Пробуем вытащить конкретное объявление из HTML
    print("\n=== Пример объявления (raw HTML) ===")
    # Ищем блок с data-marker="item"
    item_block = re.search(r'data-marker="item"[^>]*>(.*?)</div>\s*</div>\s*</div>', page, re.DOTALL)
    if item_block:
        block = item_block.group(0)[:1000]
        print(block)
    else:
        # Ищем любой блок с "item" в marker
        item_block = re.search(r'(data-marker="item[^"]*"[^>]*>)', page)
        if item_block:
            # Показываем окружающий контекст
            start = item_block.start()
            print(f"Context around first item marker:")
            print(page[start:start + 800])

    # 7. Смотрим структуру крупных data-* атрибутов
    print("\n=== Крупные data-* атрибуты ===")
    for match in re.finditer(r'data-([\w-]+)="([^"]{200,})"', page):
        name = match.group(1)
        value = match.group(2)[:200]
        print(f"  data-{name} ({len(match.group(2))} chars): {value}...")

    s.close()


asyncio.run(test())
