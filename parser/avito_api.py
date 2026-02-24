import asyncio
import logging
import random
from typing import Any

from curl_cffi.requests import AsyncSession

import config
from parser.proxy_manager import ProxyManager

logger = logging.getLogger(__name__)

BROWSER_PROFILES = [
    "chrome131",
    "chrome133a",
    "chrome136",
    "chrome142",
    "safari18_0",
    "safari18_2",
]


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


ITEMS_ENDPOINT = "https://m.avito.ru/api/9/items"
ITEM_DETAIL_ENDPOINT = "https://m.avito.ru/api/15/items/{ad_id}"


class AvitoAPI:
    def __init__(self, proxy_manager: ProxyManager) -> None:
        self.proxy_manager = proxy_manager
        self._session: AsyncSession | None = None
        self._current_profile: str | None = None

    async def _ensure_session(self) -> AsyncSession:
        """Create or recreate session with a fresh browser fingerprint."""
        if self._session is not None:
            try:
                self._session.close()
            except Exception:
                pass

        self._current_profile = random.choice(BROWSER_PROFILES)
        proxy_url = self.proxy_manager.get_proxy()
        proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None

        self._session = AsyncSession(
            impersonate=self._current_profile,
            proxies=proxies,
            timeout=30,
        )

        # Pre-warm: visit the main page to get cookies (like a real user)
        try:
            await self._session.get(
                "https://m.avito.ru/",
                headers={"Accept-Language": "ru-RU,ru;q=0.9"},
            )
        except Exception:
            pass  # best-effort

        logger.debug(
            "New session: profile=%s, proxy=%s",
            self._current_profile,
            proxy_url or "none",
        )
        return self._session

    async def _get_session(self) -> AsyncSession:
        if self._session is None:
            return await self._ensure_session()
        return self._session

    async def close(self) -> None:
        if self._session is not None:
            try:
                self._session.close()
            except Exception:
                pass
            self._session = None

    async def _request(self, url: str, params: dict | None = None) -> dict | None:
        session = await self._get_session()

        # Do NOT set User-Agent — curl_cffi sets it automatically to match
        # the impersonate profile. A mismatched UA = instant block.
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8",
            "Referer": "https://m.avito.ru/",
        }

        for attempt in range(3):
            try:
                response = await session.get(
                    url, params=params, headers=headers,
                )

                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 429:
                    delay = 20 * (attempt + 1)
                    logger.warning(
                        "HTTP 429 rate limited, pausing %ds (attempt %d/3)",
                        delay, attempt + 1,
                    )
                    # Rotate BOTH proxy AND fingerprint
                    self.proxy_manager.force_rotate()
                    session = await self._ensure_session()
                    await asyncio.sleep(delay)
                elif response.status_code in (301, 302, 403):
                    delay = 15 * (attempt + 1)
                    logger.warning(
                        "HTTP %d blocked, rotating session (attempt %d/3)",
                        response.status_code, attempt + 1,
                    )
                    self.proxy_manager.force_rotate()
                    session = await self._ensure_session()
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "HTTP %d from %s", response.status_code, url
                    )
                    return None
            except Exception as e:
                logger.warning(
                    "Request error on attempt %d: %s", attempt + 1, e,
                )
                self.proxy_manager.force_rotate()
                session = await self._ensure_session()
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
