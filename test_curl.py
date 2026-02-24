import asyncio
import re
import json
from urllib.parse import unquote
from curl_cffi.requests import AsyncSession

PROXY = "http://cmdkdzgdyfbkpzc226887-country-RU-package-mobile:uzoiutnqjy@eum.proxydoe.com:8000"


def find_items_recursive(obj, depth=0, path=""):
    """Рекурсивно ищем массивы с объявлениями."""
    if depth > 8:
        return
    if isinstance(obj, dict):
        # Если есть ключ items/listings и это список
        for key in obj:
            if key.lower() in ("items", "listings", "adverts", "list", "catalogitems", "results"):
                val = obj[key]
                if isinstance(val, list) and len(val) > 0:
                    print(f"\n  FOUND: {path}.{key} ({len(val)} items)")
                    # Показываем первый элемент
                    first = val[0]
                    if isinstance(first, dict):
                        print(f"    Keys: {list(first.keys())[:15]}")
                        # Ищем title/price
                        for k in ["title", "name", "price", "id", "itemId", "url"]:
                            if k in first:
                                print(f"    {k}: {first[k]}")
                        # Если есть вложенный value
                        if "value" in first and isinstance(first["value"], dict):
                            v = first["value"]
                            print(f"    value.keys: {list(v.keys())[:15]}")
                            for k in ["title", "name", "price", "id", "itemId", "uri"]:
                                if k in v:
                                    print(f"    value.{k}: {v[k]}")
            find_items_recursive(obj[key], depth + 1, f"{path}.{key}")
    elif isinstance(obj, list) and len(obj) > 3:
        for i, item in enumerate(obj[:2]):
            find_items_recursive(item, depth + 1, f"{path}[{i}]")


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
    print(f"Status: {r.status_code}")
    page = r.text

    # Извлекаем window.__preloadedState__ (URL-encoded)
    print("\n=== Декодируем __preloadedState__ ===")
    match = re.search(r'window\.__preloadedState__\s*=\s*"(.*?)";', page, re.DOTALL)
    if match:
        encoded = match.group(1)
        print(f"Encoded length: {len(encoded)} chars")

        decoded = unquote(encoded)
        print(f"Decoded length: {len(decoded)} chars")

        try:
            state = json.loads(decoded)
            top_keys = list(state.keys())
            print(f"Top-level keys ({len(top_keys)}): {top_keys[:20]}")

            # Сохраняем полный state
            with open("/root/avto-parser/debug_state.json", "w") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            print("Saved to debug_state.json")

            # Рекурсивно ищем items/listings
            print("\n=== Поиск объявлений ===")
            find_items_recursive(state)

            # Также проверяем ключи второго уровня
            print("\n=== Ключи второго уровня ===")
            for key in top_keys:
                if isinstance(state[key], dict):
                    sub_keys = list(state[key].keys())[:10]
                    print(f"  {key}: {sub_keys}")
                elif isinstance(state[key], list):
                    print(f"  {key}: list ({len(state[key])} items)")
                else:
                    val_str = str(state[key])[:80]
                    print(f"  {key}: {val_str}")

        except json.JSONDecodeError as e:
            print(f"JSON error: {e}")
            print(f"First 500 chars: {decoded[:500]}")
    else:
        print("__preloadedState__ not found!")

    s.close()


asyncio.run(test())
