import asyncio
import re
import json
from curl_cffi.requests import AsyncSession

PROXY = "http://cmdkdzgdyfbkpzc226887-country-RU-package-mobile:uzoiutnqjy@eum.proxydoe.com:8000"


async def test():
    s = AsyncSession(
        impersonate="chrome136",
        proxies={"http": PROXY, "https": PROXY},
        timeout=30,
    )

    # Прогрев
    await s.get("https://m.avito.ru/", headers={"Accept-Language": "ru-RU,ru;q=0.9"})
    await asyncio.sleep(2)

    # Загружаем страницу поиска
    print("=== Загрузка страницы поиска ===")
    r = await s.get(
        "https://www.avito.ru/all?q=iphone+15",
        headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9",
        },
    )
    print(f"Status: {r.status_code}")
    print(f"Page length: {len(r.text)} chars")

    html = r.text

    # Сохраняем HTML для анализа
    with open("/root/avto-parser/debug_page.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("HTML saved to debug_page.html")

    # Ищем все window.* переменные
    print("\n=== window.* переменные ===")
    for match in re.finditer(r'window\.(\w+)\s*=', html):
        print(f"  window.{match.group(1)}")

    # Ищем все <script> теги с данными
    print("\n=== script теги с JSON ===")
    for match in re.finditer(r'<script[^>]*>(.*?)</script>', html, re.DOTALL):
        content = match.group(1).strip()
        if len(content) > 500 and ('{' in content or '[' in content):
            preview = content[:200].replace('\n', ' ')
            print(f"  [{len(content)} chars] {preview}...")

    # Ищем data-* атрибуты с JSON
    print("\n=== data-* атрибуты с JSON ===")
    for match in re.finditer(r'data-(\w+)="(\{[^"]{100,})"', html):
        name = match.group(1)
        data = match.group(2)[:150]
        print(f"  data-{name}: {data}...")

    # Ищем цены (подтверждение что данные есть)
    print("\n=== Цены на странице ===")
    prices = re.findall(r'(\d[\d\s]{2,8})\s*₽', html)
    for p in prices[:10]:
        print(f"  {p} ₽")

    # Ищем ссылки на объявления
    print("\n=== Ссылки на объявления ===")
    links = re.findall(r'href="(/[^"]*_(\d{8,})[^"]*)"', html)
    for link, ad_id in links[:5]:
        print(f"  ad_id={ad_id}: {link}")

    # Ищем ключевые слова в HTML
    print("\n=== Ключевые слова ===")
    keywords = [
        "iphone", "iPhone", "price", "title",
        "catalogItems", "searchResult", "initialState",
        "serverState", "apolloState", "preloadedData",
        "SSR_DATA", "INITIAL_STATE", "__PRELOADED",
    ]
    for kw in keywords:
        count = html.count(kw)
        if count > 0:
            print(f"  '{kw}': {count} times")
            # Показать контекст первого вхождения
            idx = html.find(kw)
            context = html[max(0, idx - 50):idx + 80].replace('\n', ' ')
            print(f"    context: ...{context}...")

    await s.aclose()


asyncio.run(test())
