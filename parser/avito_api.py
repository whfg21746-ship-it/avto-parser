import asyncio
import logging
import random
from typing import Any

import aiohttp

import config
from parser.proxy_manager import ProxyManager

logger = logging.getLogger(__name__)


def _extract_price(raw: Any) -> int:
    """Extract integer price from various Avito response formats."""
    if isinstance(raw, (int, float)):
        return int(raw)
    if isinstance(raw, dict):
        return int(raw.get("value", raw.get("price", 0)))
    if isinstance(raw, str):
        cleaned = raw.replace(" ", "").replace("\u20bd", "").replace("\xa0", "")
        try:
            return int(cleaned)
        except ValueError:
            return 0
    return 0

_USER_AGENTS = [
    "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SM-A546B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; 2201116SG) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/131.0.6778.73 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 13; M2101K6G) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; RMX3085) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
]


def _random_headers() -> dict[str, str]:
    return {
        "User-Agent": random.choice(_USER_AGENTS),
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8",
        "Referer": "https://m.avito.ru/",
    }

ITEMS_ENDPOINT = "https://m.avito.ru/api/9/items"
ITEM_DETAIL_ENDPOINT = "https://m.avito.ru/api/15/items/{ad_id}"


class AvitoAPI:
    def __init__(self, proxy_manager: ProxyManager) -> None:
        self.proxy_manager = proxy_manager
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            jar = aiohttp.CookieJar()
            self._session = aiohttp.ClientSession(
                timeout=timeout, cookie_jar=jar
            )
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def _request(self, url: str, params: dict | None = None) -> dict | None:
        session = await self._get_session()
        proxy = self.proxy_manager.get_proxy()

        for attempt in range(3):
            try:
                headers = _random_headers()
                async with session.get(
                    url, params=params, proxy=proxy,
                    headers=headers, allow_redirects=False,
                ) as resp:
                    if resp.status == 200:
                        return await resp.json(content_type=None)
                    elif resp.status == 429:
                        delay = 20 * (attempt + 1)
                        logger.warning(
                            "HTTP 429 rate limited, pausing %ds (attempt %d/3)",
                            delay, attempt + 1,
                        )
                        self.proxy_manager.force_rotate()
                        proxy = self.proxy_manager.get_proxy()
                        await asyncio.sleep(delay)
                    elif resp.status in (301, 302, 403):
                        delay = 15 * (attempt + 1)
                        logger.warning(
                            "HTTP %d blocked, switching proxy (attempt %d/3)",
                            resp.status, attempt + 1,
                        )
                        self.proxy_manager.force_rotate()
                        proxy = self.proxy_manager.get_proxy()
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            "HTTP %d from %s", resp.status, url
                        )
                        return None
            except asyncio.TimeoutError:
                logger.warning("Timeout on attempt %d for %s", attempt + 1, url)
                await asyncio.sleep(15)
            except aiohttp.ClientError as e:
                logger.warning(
                    "Client error on attempt %d: %s", attempt + 1, e
                )
                await asyncio.sleep(15)

        logger.error("All retries exhausted for %s", url)
        return None

    async def search_by_keyword(self, search_query: dict) -> list[dict]:
        """Search Avito listings using a broad keyword query.

        Args:
            search_query: dict with keys: keyword, avito_category_id, price_max
        """
        params = {
            "key": config.AVITO_API_KEY,
            "locationId": config.AVITO_LOCATION_ID,
            "query": search_query["keyword"],
            "sort": "date",
            "withImagesOnly": 1,
            "privateOnly": 1,
            "limit": 50,
            "page": 1,
            "display": "list",
        }

        if search_query.get("avito_category_id"):
            params["categoryId"] = search_query["avito_category_id"]

        if search_query.get("price_max"):
            params["priceMax"] = search_query["price_max"]

        data = await self._request(ITEMS_ENDPOINT, params)
        if not data:
            return []

        results = []
        for entry in data.get("result", {}).get("items", []):
            if entry.get("type") != "item":
                continue
            value = entry.get("value", {})
            ad_id = str(value.get("id", ""))
            if not ad_id:
                continue

            # Extract listing params/attributes from search results
            listing_params = {}
            for param in value.get("params", []):
                if isinstance(param, dict):
                    title = param.get("title", "")
                    val = param.get("value", "")
                    if title and val:
                        listing_params[title] = val

            results.append({
                "ad_id": ad_id,
                "title": value.get("title", ""),
                "price": _extract_price(value.get("price", 0)),
                "url": f"https://www.avito.ru{value.get('uri', '')}",
                "city": value.get("location", {}).get("name", ""),
                "params": listing_params,
            })

        return results

    async def get_item_details(self, ad_id: str) -> dict | None:
        """Fetch full details for a specific listing."""
        url = ITEM_DETAIL_ENDPOINT.format(ad_id=ad_id)
        params = {"key": config.AVITO_API_KEY}

        data = await self._request(url, params)
        if not data:
            return None

        result = {}
        result["ad_id"] = ad_id
        result["title"] = data.get("title", "")
        result["description"] = data.get("description", "")
        result["price"] = _extract_price(data.get("price", 0))
        result["url"] = data.get("url", f"https://www.avito.ru/{ad_id}")
        result["city"] = data.get("location", {}).get("name", "")

        # Seller info
        seller = data.get("seller", {})
        result["seller_type"] = "private" if "\u0427\u0430\u0441\u0442\u043d\u043e\u0435" in seller.get("postfix", "") else "shop"
        result["seller_items_count"] = seller.get("itemsCount", 0)
        result["seller_closed_items"] = seller.get("closedItemsCount", 0)

        # Images
        images = data.get("images", [])
        result["images"] = [img.get("640x480", "") for img in images if img.get("640x480")]

        # Params/attributes as string
        params_list = []
        for param in data.get("params", []):
            title = param.get("title", "")
            value = param.get("value", "")
            if title and value:
                params_list.append(f"{title}: {value}")
        result["params_str"] = ", ".join(params_list) if params_list else "N/A"

        return result

    async def delay(self) -> None:
        """Random delay between requests."""
        await asyncio.sleep(random.uniform(4.0, 8.0))
