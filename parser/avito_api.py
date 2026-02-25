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


def _deep_find_description(data: dict, max_depth: int = 3, _depth: int = 0) -> str:
    """Recursively search for a 'description' key in nested dicts."""
    if _depth > max_depth:
        return ""
    for key, value in data.items():
        if key == "description" and isinstance(value, str) and len(value) > 20:
            return value
        if isinstance(value, dict):
            result = _deep_find_description(value, max_depth, _depth + 1)
            if result:
                return result
    return ""


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
                await self._session.close()
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
                await self._session.close()
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

    @staticmethod
    def _get_embedded_redirect(data: dict) -> str | None:
        """Check if the embedded JSON contains a suspense redirect.

        Avito often redirects keyword searches to specific category URLs
        via a client-side redirect embedded in the JSON data (status 301).
        """
        # Check state.redirect (top-level redirect URL)
        redirect = data.get("redirect")
        if redirect and isinstance(redirect, str) and redirect.startswith("/"):
            return redirect

        # Check state.data.url (redirect target in data section)
        inner = data.get("data", {})
        if isinstance(inner, dict):
            status = inner.get("status", {})
            if isinstance(status, dict) and status.get("code") in (301, 302):
                redirect_url = inner.get("url")
                if redirect_url and isinstance(redirect_url, str):
                    return redirect_url

        return None

    async def _fetch_page_with_redirects(self, url: str, max_redirects: int = 3) -> tuple[dict, str]:
        """Fetch a page and follow embedded redirects.

        Returns (extracted_json_data, final_url).
        """
        current_url = url
        for i in range(max_redirects + 1):
            html_text = await self._fetch_html(current_url)
            if not html_text:
                return {}, current_url

            data = self._extract_json_from_html(html_text)
            if not data:
                return {}, current_url

            redirect = self._get_embedded_redirect(data)
            if redirect and i < max_redirects:
                new_url = f"{BASE_URL}{redirect}" if redirect.startswith("/") else redirect
                logger.info("Following embedded redirect: %s -> %s", current_url, new_url)
                current_url = new_url
                await asyncio.sleep(1)
                continue

            return data, current_url

        return {}, current_url

    def _parse_items_from_data(self, data: dict) -> list[dict]:
        """Parse listings from extracted JSON data."""
        raw_items = self._find_catalog_items(data)
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

            results.append({
                "ad_id": ad_id,
                "title": item.get("title", ""),
                "price": price,
                "url": full_url,
                "city": city,
                # Store full raw item for get_item_details()
                "_raw": item,
            })
        return results

    async def search_by_keyword(
        self, search_query: dict, max_pages: int = 3,
    ) -> list[dict]:
        """Search Avito by scraping search results pages.

        Args:
            search_query: dict with keys:
                keyword     – search keyword (always present)
                avito_url   – full Avito URL (optional, takes priority)
                price_max   – maximum price filter (optional)
            max_pages: how many search pages to fetch (default 3)
        Returns:
            list of dicts with: ad_id, title, price, url, city, params
        """
        avito_url = search_query.get("avito_url")
        if avito_url:
            base_url = self._set_page(avito_url, 1)
        else:
            base_url = self._build_search_url(
                keyword=search_query["keyword"],
                price_max=search_query.get("price_max"),
            )

        all_results: list[dict] = []
        seen_ids: set[str] = set()

        for page_num in range(1, max_pages + 1):
            page_url = self._set_page(base_url, page_num) if page_num > 1 else base_url

            data, final_url = await self._fetch_page_with_redirects(page_url)
            if not data:
                if page_num == 1:
                    logger.warning("No embedded JSON found on search page")
                break

            page_results = self._parse_items_from_data(data)
            if not page_results:
                if page_num == 1:
                    logger.warning(
                        "No items found in catalog data (url=%s, keys=%s)",
                        final_url, list(data.keys())[:10],
                    )
                break

            # Deduplicate across pages
            new_count = 0
            for item in page_results:
                if item["ad_id"] not in seen_ids:
                    seen_ids.add(item["ad_id"])
                    all_results.append(item)
                    new_count += 1

            logger.info(
                "Page %d: %d items (%d new, %d total)",
                page_num, len(page_results), new_count, len(all_results),
            )

            # If page returned very few new items, no point fetching more
            if new_count < 3:
                break

            # Delay between pages
            if page_num < max_pages:
                await asyncio.sleep(random.uniform(2.0, 5.0))

        logger.info("Extracted %d total listings from %d page(s)", len(all_results), min(page_num, max_pages))
        return all_results

    @staticmethod
    def _extract_seller_closed(text: str) -> int:
        """Parse '112 завершённых объявлений' -> 112."""
        if not text:
            return 0
        match = re.search(r"(\d+)", text)
        return int(match.group(1)) if match else 0

    @staticmethod
    def _extract_images(item: dict) -> list[str]:
        """Extract image URLs from search item data."""
        urls: list[str] = []

        # Try gallery.image_large_urls first (best quality)
        gallery = item.get("gallery", {})
        if isinstance(gallery, dict):
            for key in ("image_large_urls", "image_urls"):
                img_list = gallery.get(key, [])
                if isinstance(img_list, list) and img_list:
                    urls = [str(u) for u in img_list if u]
                    if urls:
                        return urls
            # Single large image
            for key in ("imageLargeUrl", "imageUrl"):
                val = gallery.get(key)
                if val and isinstance(val, str) and val.startswith("http"):
                    urls.append(val)

        # Fallback: images list with size dicts
        images = item.get("images", [])
        if isinstance(images, list):
            for img in images:
                if isinstance(img, dict):
                    for size in ("640x480", "1280x960", "208x156"):
                        val = img.get(size)
                        if val:
                            urls.append(str(val))
                            break
                elif isinstance(img, str) and img.startswith("http"):
                    urls.append(img)

        return urls

    @staticmethod
    def _extract_params_str(item: dict) -> str:
        """Extract human-readable params string from IVA components."""
        parts: list[str] = []
        iva = item.get("iva")
        if not isinstance(iva, dict):
            return "N/A"

        for step_name in ("DescriptionStep", "FirstLineStep", "ThirdLineStep", "FourthLineStep"):
            steps = iva.get(step_name)
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
                    if text and isinstance(text, str) and len(text) < 200:
                        parts.append(text)

        return ", ".join(parts) if parts else "N/A"

    @staticmethod
    def extract_listing_params(raw_item: dict) -> dict[str, str]:
        """Extract key-value params from IVA components for model matching.

        Returns a dict suitable for match_listing_to_item() / extract_storage_from_listing().
        """
        params: dict[str, str] = {}
        iva = raw_item.get("iva")
        if not isinstance(iva, dict):
            return params

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
                    if text and isinstance(text, str) and len(text) < 200:
                        params[f"iva_{len(params)}"] = text
        return params

    def get_item_details(self, ad_id: str, raw_item: dict | None = None, **kwargs: Any) -> dict:
        """Extract full details from a search result item.

        Avito detail pages are fully client-side rendered (no embedded JSON),
        but search results already contain all needed data: description,
        images, seller info, params, etc.

        Args:
            ad_id: listing ID
            raw_item: the full raw item dict from search results (_raw field)
        """
        if raw_item is None:
            raw_item = {}

        url_path = raw_item.get("urlPath", "")
        full_url = f"{BASE_URL}{url_path}" if url_path else kwargs.get("url", "")

        # Price
        price = 0
        price_data = raw_item.get("priceDetailed")
        if isinstance(price_data, dict):
            price = _extract_price(price_data.get("value", 0))

        # Location
        location = raw_item.get("location", {})
        city = location.get("name", "") if isinstance(location, dict) else ""

        # Seller type from userLogo
        seller_type = "private"
        user_logo = raw_item.get("userLogo", {})
        if isinstance(user_logo, dict) and user_logo.get("developerId"):
            seller_type = "shop"

        # Seller active items count — try multiple possible field names
        seller_active_items = 0
        for field in ("itemsText", "activeItemsText", "sellerItemsText"):
            text = raw_item.get(field, "")
            if text:
                seller_active_items = self._extract_seller_closed(text)
                break

        # Also check inside userLogo for items count
        if not seller_active_items and isinstance(user_logo, dict):
            for field in ("itemsCount", "activeItems", "totalItems"):
                val = user_logo.get(field)
                if isinstance(val, (int, float)) and val > 0:
                    seller_active_items = int(val)
                    break

        if not seller_active_items:
            # Log available keys once per ad for debugging
            seller_keys = [
                k for k in raw_item
                if any(w in k.lower() for w in ("item", "seller", "user", "closed", "active", "count"))
            ]
            if seller_keys:
                logger.debug(
                    "ad_id=%s seller-related keys: %s", ad_id, seller_keys,
                )

        # Images
        images = self._extract_images(raw_item)

        # Params
        params_str = self._extract_params_str(raw_item)

        # Sort timestamp (for freshness filtering)
        sort_timestamp = raw_item.get("sortTimeStamp", 0)

        return {
            "ad_id": ad_id,
            "title": raw_item.get("title", ""),
            "description": raw_item.get("description", ""),
            "price": price,
            "url": full_url,
            "city": city,
            "seller_type": seller_type,
            "seller_active_items": seller_active_items,
            "sort_timestamp": sort_timestamp,
            "images": images,
            "params_str": params_str,
        }

    async def fetch_ad_description(self, ad_url: str) -> str:
        """Fetch the ad detail page and extract the full description.

        Search results don't include descriptions, so we load
        the actual ad page to get it from embedded JSON.
        """
        if not ad_url:
            return ""

        html_text = await self._fetch_html(ad_url)
        if not html_text:
            return ""

        data = self._extract_json_from_html(html_text)
        if not data:
            logger.debug("No embedded JSON on ad page: %s", ad_url)
            return ""

        description = self._extract_description_from_ad_data(data)
        if description:
            logger.debug(
                "Fetched description (%d chars) from %s",
                len(description), ad_url,
            )
        return description

    @staticmethod
    def _extract_description_from_ad_data(data: dict) -> str:
        """Navigate ad page JSON to find the description field."""
        # Path 1: state.item.description (most common)
        item = data.get("item", {})
        if isinstance(item, dict):
            desc = item.get("description")
            if desc and isinstance(desc, str) and len(desc) > 5:
                return desc.strip()

        # Path 2: data.item.description
        inner = data.get("data", {})
        if isinstance(inner, dict):
            inner_item = inner.get("item", {})
            if isinstance(inner_item, dict):
                desc = inner_item.get("description")
                if desc and isinstance(desc, str) and len(desc) > 5:
                    return desc.strip()

        # Path 3: buyerItem / cardItem / viewItem
        for key in ("buyerItem", "cardItem", "viewItem"):
            obj = data.get(key, {})
            if isinstance(obj, dict):
                desc = obj.get("description")
                if desc and isinstance(desc, str) and len(desc) > 5:
                    return desc.strip()

        # Path 4: deep search in nested dicts (max 3 levels)
        desc = _deep_find_description(data, max_depth=3)
        if desc:
            return desc.strip()

        return ""

    async def fetch_ad_extra(self, ad_url: str) -> dict:
        """Fetch ad page and extract description + seller active items.

        Returns dict with 'description' and 'seller_active_items' keys.
        """
        result = {"description": "", "seller_active_items": 0}
        if not ad_url:
            return result

        html_text = await self._fetch_html(ad_url)
        if not html_text:
            return result

        data = self._extract_json_from_html(html_text)
        if not data:
            return result

        result["description"] = self._extract_description_from_ad_data(data)

        # Try to extract seller active items from ad page
        seller_count = self._extract_seller_items_from_ad_data(data)
        if seller_count > 0:
            result["seller_active_items"] = seller_count

        return result

    @staticmethod
    def _extract_seller_items_from_ad_data(data: dict) -> int:
        """Try to extract seller's active items count from the ad detail page."""
        for key in ("seller", "sellerInfo", "userInfo", "user"):
            seller = data.get(key, {})
            if not isinstance(seller, dict):
                continue
            for field in ("itemsCount", "activeItems", "totalItems",
                          "itemsActive"):
                val = seller.get(field)
                if isinstance(val, (int, float)) and val > 0:
                    return int(val)
            # Try text field: "112 объявлений"
            for field in ("itemsText", "activeItemsText"):
                text = seller.get(field, "")
                if text:
                    match = re.search(r"(\d+)", str(text))
                    if match:
                        return int(match.group(1))

        # Check nested data.seller
        inner = data.get("data", {})
        if isinstance(inner, dict):
            for key in ("seller", "sellerInfo"):
                seller = inner.get(key, {})
                if isinstance(seller, dict):
                    for field in ("itemsCount", "activeItems", "totalItems"):
                        val = seller.get(field)
                        if isinstance(val, (int, float)) and val > 0:
                            return int(val)

        return 0

    async def delay(self) -> None:
        """Random delay between requests."""
        await asyncio.sleep(random.uniform(4.0, 8.0))
