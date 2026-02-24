import asyncio
import re
import json
from urllib.parse import unquote
from curl_cffi.requests import AsyncSession

PROXY = "http://cmdkdzgdyfbkpzc226887-country-RU-package-mobile:uzoiutnqjy@eum.proxydoe.com:8000"


def deep_explore(obj, path="root", depth=0, max_depth=6):
    """Рекурсивно показываем структуру JSON."""
    if depth > max_depth:
        return
    if isinstance(obj, dict):
        for key in list(obj.keys())[:30]:
            val = obj[key]
            if isinstance(val, dict):
                size = len(json.dumps(val))
                print(f"{'  ' * depth}{path}.{key}: dict({len(val)} keys, {size} bytes)")
                if size > 500:
                    deep_explore(val, f"{path}.{key}", depth + 1, max_depth)
            elif isinstance(val, list):
                print(f"{'  ' * depth}{path}.{key}: list({len(val)} items)")
                if len(val) > 0 and isinstance(val[0], dict):
                    print(f"{'  ' * (depth + 1)}[0] keys: {list(val[0].keys())[:15]}")
                    for k in ["title", "name", "price", "id", "itemId", "url", "uri", "type"]:
                        if k in val[0]:
                            print(f"{'  ' * (depth + 1)}[0].{k}: {str(val[0][k])[:100]}")
                if size_of_list(val) > 500:
                    deep_explore(val[0] if val and isinstance(val[0], dict) else {}, f"{path}.{key}[0]", depth + 1, max_depth)
            elif isinstance(val, str) and len(val) > 200:
                print(f"{'  ' * depth}{path}.{key}: str({len(val)} chars) = {val[:100]}...")
            else:
                val_str = str(val)[:100]
                print(f"{'  ' * depth}{path}.{key}: {val_str}")


def size_of_list(lst):
    try:
        return len(json.dumps(lst))
    except Exception:
        return 0


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

    # 1. __staticRouterHydrationData
    print("\n=== __staticRouterHydrationData ===")
    match = re.search(r'__staticRouterHydrationData\s*=\s*JSON\.parse\("(.+?)"\);\s*</script>', page, re.DOTALL)
    if match:
        raw = match.group(1)
        unescaped = raw.replace('\\"', '"').replace('\\\\', '\\')
        try:
            data = json.loads(unescaped)
            print("Exploring structure:")
            deep_explore(data, "router", 0, 5)
            with open("/root/avto-parser/debug_router.json", "w") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print("\nSaved to debug_router.json")
        except json.JSONDecodeError as e:
            print(f"Parse error: {e}")
    else:
        print("Not found!")

    # 2. window.__mfe__ (тоже URL-encoded)
    print("\n=== window.__mfe__ ===")
    match = re.search(r'window\.__mfe__\s*=\s*"(.*?)";', page)
    if match:
        decoded = unquote(match.group(1))
        try:
            mfe = json.loads(decoded)
            print(f"Keys: {list(mfe.keys())[:20]}")
            deep_explore(mfe, "mfe", 0, 3)
        except json.JSONDecodeError:
            print(f"Not JSON, length: {len(decoded)}")
    else:
        print("Not found!")

    # 3. Ищем внутренний API endpoint в JS коде
    print("\n=== API endpoints в JS ===")
    api_patterns = [
        r'["\'](/api/\d+/[^"\']+)["\']',
        r'["\']https?://[^"\']*avito[^"\']*api[^"\']+["\']',
        r'fetch\(["\']([^"\']+)["\']',
    ]
    found_apis = set()
    for pattern in api_patterns:
        for m in re.finditer(pattern, page):
            found_apis.add(m.group(1) if m.lastindex else m.group(0))
    for api in sorted(found_apis)[:20]:
        print(f"  {api}")

    s.close()


asyncio.run(test())
