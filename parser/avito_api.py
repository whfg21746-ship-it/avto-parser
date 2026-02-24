import asyncio
import html as html_lib
import json
import logging
import random
import re
from typing import Any
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession

from parser.cookie_provider import CookieProvider
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

BASE_URL = "https://www.avito.ru"


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


class AvitoAPI:
    """Avito scraper that extracts embedded JSON from HTML pages.

    Avito's SPA embeds catalog data in <script type="mime/invalid"> tags.
    This approach is used by Duff89/parser_avito (484+ stars, actively
    maintained) and does not require any API key.
    """

    def __init__(
        self,
        proxy_manager: ProxyManager,
        cookie_provider: CookieProvider | None = None,
    ) -> None:
        self.proxy_manager = proxy_manager
        self.cookie_provider = cookie_provider
        self._session: AsyncSession | None = None
        self._current_profile: str | None = None
        self._warmed = False

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

        # Inject Playwright cookies (including ft fingerprint) if available
        if self.cookie_provider:
            try:
                cookies = await self.cookie_provider.ensure_cookies()
                for name, value in cookies.items():
                    self._session.cookies.set(name, value, domain=".avito.ru")
                if cookies:
                    logger.debug("Injected %d cookies from provider", len(cookies))
            except Exception as e:
                logger.warning("Failed to get cookies from provider: %s", e)

        # Pre-warm: visit the main page to get server-side cookies
        if not self._warmed:
            try:
                await self._session.get(
                    BASE_URL,
                    headers={
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "Accept-Language": "ru-RU,ru;q=0.9",
                    },
                )
                self._warmed = True
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

    async def _fetch_html(self, url: str) -> str | None:
        """Fetch an HTML page with retry and rotation logic."""
        session = await self._get_session()

        # Do NOT set User-Agent — curl_cffi sets it automatically to match
        # the impersonate profile. A mismatched UA = instant block.
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        }

        for attempt in range(3):
            try:
                response = await session.get(url, headers=headers)

                if response.status_code == 200:
                    return response.text
                elif response.status_code == 429:
                    delay = 20 * (attempt + 1)
                    logger.warning(
                        "HTTP 429 rate limited, pausing %ds (attempt %d/3)",
                        delay, attempt + 1,
                    )
                    self.proxy_manager.force_rotate()
                    session = await self._ensure_session()
                    await asyncio.sleep(delay)
                elif response.status_code in (301, 302, 403):
                    delay = 15 * (attempt + 1)
                    logger.warning(
                        "HTTP %d blocked, rotating session (attempt %d/3)",
                        response.status_code, attempt + 1,
                    )
                    if self.cookie_provider:
                        self.cookie_provider.handle_block()
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

    # ------------------------------------------------------------------
    # JSON extraction from Avito HTML
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_json_from_html(html_text: str) -> dict:
        """Extract JSON data from <script type="mime/invalid"> tags.

        Avito embeds catalog/item data as JSON inside script tags with
        type="mime/invalid".  The JSON typically has a 'state' or 'data'
        top-level key.
        """
        soup = BeautifulSoup(html_text, "html.parser")

        for script in soup.select("script"):
            if script.get("type") != "mime/invalid":
                continue
            try:
                content = html_lib.unescape(script.text)
                parsed = json.loads(content)

                if "state" in parsed:
                    return parsed["state"]
                if "data" in parsed:
                    return parsed["data"]
                return parsed
            except (json.JSONDecodeError, Exception) as e:
                logger.debug("Failed to parse mime/invalid script: %s", e)

        # Fallback: try window.__initialData__ patterns
        for pattern in [
            r'window\.__initialData__\s*=\s*"(.+?)"\s*;',
            r'window\.__initialData__\s*=\s*({.+?})\s*;',
        ]:
            match = re.search(pattern, html_text, re.DOTALL)
            if match:
                try:
                    raw = match.group(1)
                    # Avito sometimes double-encodes the JSON
                    if raw.startswith('"') or raw.startswith("\\"):
                        raw = json.loads(f'"{raw}"') if not raw.startswith("{") else raw
                    data = json.loads(raw) if isinstance(raw, str) else raw
                    return data
                except Exception:
                    pass

        return {}

    @staticmethod
    def _find_catalog_items(data: dict) -> list[dict]:
        """Navigate the extracted JSON to find catalog items list."""
        # Path 1: data -> catalog -> items  (most common after find_json returns state)
        catalog = data.get("catalog", {})
        if isinstance(catalog, dict):
            items = catalog.get("items")
            if items:
                return items

        # Path 2: data -> data -> catalog -> items
        inner = data.get("data", {})
        if isinstance(inner, dict):
            catalog = inner.get("catalog", {})
            if isinstance(catalog, dict):
                items = catalog.get("items")
                if items:
                    return items

        # Path 3: items directly
        items = data.get("items")
        if items:
            return items

        return []

    # ------------------------------------------------------------------
    # URL helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_search_url(
        keyword: str,
        price_max: int | None = None,
        page: int = 1,
    ) -> str:
        """Build an Avito search URL from keyword and parameters."""
        params: dict[str, str] = {"q": keyword, "s": "104"}  # sort by date
        if price_max:
            params["pmax"] = str(price_max)
        if page > 1:
            params["p"] = str(page)
        return f"{BASE_URL}/all?{urlencode(params)}"

    @staticmethod
    def _set_page(url: str, page: int) -> str:
        """Set/replace the page number in a URL."""
        parts = urlparse(url)
        query = parse_qs(parts.query)
        if page > 1:
            query["p"] = [str(page)]
        elif "p" in query:
            del query["p"]
        new_query = urlencode(query, doseq=True)
        return urlunparse(
            (parts.scheme, parts.netloc, parts.path,
             parts.params, new_query, parts.fragment)
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def search_by_keyword(self, search_query: dict) -> list[dict]:
        """Search Avito by scraping the search results page.

        Args:
            search_query: dict with keys:
                keyword     – search keyword (always present)
                avito_url   – full Avito URL (optional, takes priority)
                price_max   – maximum price filter (optional)
        Returns:
            list of dicts with: ad_id, title, price, url, city, params
        """
        avito_url = search_query.get("avito_url")
        if avito_url:
            url = self._set_page(avito_url, 1)
        else:
            url = self._build_search_url(
                keyword=search_query["keyword"],
                price_max=search_query.get("price_max"),
            )

        html_text = await self._fetch_html(url)
        if not html_text:
            return []

        data = self._extract_json_from_html(html_text)
        if not data:
            logger.warning("No embedded JSON found on search page")
            return []

        raw_items = self._find_catalog_items(data)
        if not raw_items:
            logger.warning("No items found in catalog data (keys: %s)", list(data.keys())[:10])
            return []

        results = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue

            item_id = item.get("id")
            if not item_id or isinstance(item_id, dict):
                continue

            # Skip promoted / reserved listings
            if item.get("isPromotion"):
                continue

            ad_id = str(item_id)
            url_path = item.get("urlPath", "")
            full_url = f"{BASE_URL}{url_path}" if url_path else ""

            # Price
            price = 0
            price_detailed = item.get("priceDetailed")
            if isinstance(price_detailed, dict):
                price = _extract_price(price_detailed.get("value", 0))

            # Location
            location = item.get("location", {})
            city = location.get("name", "") if isinstance(location, dict) else ""

            # Extract listing params from IVA components (limited in search)
            listing_params: dict[str, str] = {}
            iva = item.get("iva")
            if isinstance(iva, dict):
                for steps in iva.values():
                    if not isinstance(steps, list):
                        continue
                    for step in steps:
                        if not isinstance(step, dict):
                            continue
                        cd = step.get("componentData", {})
                        if not isinstance(cd, dict):
                            continue
                        payload = cd.get("payload", {})
                        if isinstance(payload, dict):
                            text = payload.get("text", "")
                            if text and isinstance(text, str):
                                listing_params["info"] = text

            results.append({
                "ad_id": ad_id,
                "title": item.get("title", ""),
                "price": price,
                "url": full_url,
                "city": city,
                "params": listing_params,
            })

        logger.info("Extracted %d listings from search page", len(results))
        return results

    async def get_item_details(self, ad_id: str, url: str = "") -> dict | None:
        """Fetch full details for a specific listing.

        Loads the listing HTML page and extracts embedded JSON.
        """
        if not url:
            url = f"{BASE_URL}/{ad_id}"

        html_text = await self._fetch_html(url)
        if not html_text:
            return None

        data = self._extract_json_from_html(html_text)
        if not data:
            logger.warning("No embedded JSON found on item page %s", ad_id)
            return None

        # The item page JSON may nest the item data under various keys
        item_data = data.get("item", data)

        result: dict[str, Any] = {
            "ad_id": ad_id,
            "title": item_data.get("title", ""),
            "description": item_data.get("description", ""),
            "price": 0,
            "url": url,
            "city": "",
            "seller_type": "private",
            "seller_items_count": 0,
            "seller_closed_items": 0,
            "images": [],
            "params_str": "N/A",
        }

        # Price
        price_data = item_data.get("priceDetailed") or item_data.get("price")
        if isinstance(price_data, dict):
            result["price"] = _extract_price(price_data.get("value", 0))
        elif isinstance(price_data, (int, float)):
            result["price"] = int(price_data)

        # Location
        location = item_data.get("location", {})
        if isinstance(location, dict):
            result["city"] = location.get("name", "")

        # Seller
        seller = item_data.get("seller", {})
        if isinstance(seller, dict):
            result["seller_items_count"] = seller.get("itemsCount", 0)
            result["seller_closed_items"] = seller.get("closedItemsCount", 0)
            postfix = seller.get("postfix", "")
            if "\u0427\u0430\u0441\u0442\u043d\u043e\u0435" in postfix:
                result["seller_type"] = "private"
            else:
                result["seller_type"] = "shop"

        # Images
        images = item_data.get("images", [])
        if isinstance(images, list):
            for img in images:
                if isinstance(img, dict):
                    for size in ("640x480", "1280x960"):
                        val = img.get(size)
                        if val:
                            result["images"].append(str(val))
                            break

        # Params / attributes
        params_raw = item_data.get("params", [])
        if isinstance(params_raw, list):
            parts = []
            for p in params_raw:
                if isinstance(p, dict):
                    title = p.get("title", "")
                    value = p.get("value", "")
                    if title and value:
                        parts.append(f"{title}: {value}")
            if parts:
                result["params_str"] = ", ".join(parts)

        return result

    async def delay(self) -> None:
        """Random delay between requests."""
        await asyncio.sleep(random.uniform(4.0, 8.0))
