"""Avito parameter auto-discovery module.

Discovers the correct categoryId and params[N]=value filters
for product models by querying Avito's search API and web parsing.
"""

import asyncio
import logging
import random
import re
from typing import Any

from curl_cffi.requests import AsyncSession

import config
from parser.avito_api import BROWSER_PROFILES
from parser.proxy_manager import ProxyManager

logger = logging.getLogger(__name__)

ITEMS_ENDPOINT = "https://m.avito.ru/api/9/items"


class ParamDiscovery:
    """Discovers Avito API parameters for product models."""

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

        # Pre-warm session
        try:
            await self._session.get(
                "https://m.avito.ru/",
                headers={"Accept-Language": "ru-RU,ru;q=0.9"},
            )
        except Exception:
            pass

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
                        "Discovery: HTTP 429, pausing %ds (attempt %d/3)",
                        delay, attempt + 1,
                    )
                    self.proxy_manager.force_rotate()
                    session = await self._ensure_session()
                    await asyncio.sleep(delay)
                elif response.status_code in (301, 302, 403):
                    delay = 15 * (attempt + 1)
                    logger.warning(
                        "Discovery: HTTP %d, rotating session (attempt %d/3)",
                        response.status_code, attempt + 1,
                    )
                    self.proxy_manager.force_rotate()
                    session = await self._ensure_session()
                    await asyncio.sleep(delay)
                else:
                    logger.warning(
                        "Discovery: HTTP %d from %s", response.status_code, url
                    )
                    return None
            except Exception as e:
                logger.warning(
                    "Discovery: request error attempt %d: %s", attempt + 1, e,
                )
                self.proxy_manager.force_rotate()
                session = await self._ensure_session()
                await asyncio.sleep(15)

        return None

    async def _request_text(self, url: str, params: dict | None = None) -> str | None:
        session = await self._get_session()

        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8",
            "Referer": "https://www.avito.ru/",
        }

        for attempt in range(3):
            try:
                response = await session.get(
                    url, params=params, headers=headers,
                )

                if response.status_code == 200:
                    return response.text
                elif response.status_code in (301, 302, 403, 429):
                    delay = 20 * (attempt + 1) if response.status_code == 429 else 15 * (attempt + 1)
                    self.proxy_manager.force_rotate()
                    session = await self._ensure_session()
                    await asyncio.sleep(delay)
                else:
                    return None
            except Exception as e:
                logger.warning(
                    "Discovery: text request error attempt %d: %s", attempt + 1, e,
                )
                self.proxy_manager.force_rotate()
                session = await self._ensure_session()
                await asyncio.sleep(15)

        return None

    async def discover_via_search(self, query: str) -> dict | None:
        """Method B: Search items API and extract category/params from response."""
        params = {
            "key": config.AVITO_API_KEY,
            "query": query,
            "locationId": config.AVITO_LOCATION_ID,
            "limit": 5,
            "sort": "date",
        }

        data = await self._request(ITEMS_ENDPOINT, params)
        if not data:
            return None

        result = self._parse_search_response(data, query)
        if result:
            result["discovered_via"] = "search_api"
            result["raw_response"] = data
            return result

        return None

    def _parse_search_response(self, data: dict, query: str) -> dict | None:
        """Parse search API response to extract category info."""
        result_data = data.get("result", {})

        # Check for mainCategory or category info
        main_category = result_data.get("mainCategory", {})
        category_id = main_category.get("id") if isinstance(main_category, dict) else None

        # Check refs section for categories
        if not category_id:
            refs = data.get("refs", result_data.get("refs", {}))
            if isinstance(refs, dict):
                categories = refs.get("categories", [])
                if isinstance(categories, list) and categories:
                    category_id = categories[0].get("id")

        # Check searchParameters / appliedParams
        params = {}
        search_params = result_data.get("searchParameters", result_data.get("appliedParams", {}))
        if isinstance(search_params, dict):
            for key, value in search_params.items():
                if key.startswith("params["):
                    params[key] = str(value)

        # Also check the "filters" section for applied filter values
        filters = result_data.get("filters", result_data.get("appliedFilters", []))
        if isinstance(filters, list):
            for f in filters:
                if not isinstance(f, dict):
                    continue
                param_key = f.get("key", f.get("id", ""))
                param_value = f.get("value", f.get("selectedValue"))
                if param_key and param_value and str(param_key).isdigit():
                    params[f"params[{param_key}]"] = str(param_value)

        # Try to get category from items if not found yet
        if not category_id:
            items = result_data.get("items", [])
            for item in items:
                if not isinstance(item, dict):
                    continue
                value = item.get("value", item)
                cat = value.get("categoryId", value.get("category_id"))
                if cat:
                    try:
                        category_id = int(cat)
                        break
                    except (ValueError, TypeError):
                        pass

        if category_id:
            try:
                category_id = int(category_id)
            except (ValueError, TypeError):
                category_id = None

        if category_id or params:
            return {
                "category_id": category_id,
                "params": params,
            }

        return None

    async def discover_via_web(self, query: str) -> dict | None:
        """Method C: Parse Avito web page for embedded search config."""
        url = f"https://www.avito.ru/all?q={query.replace(' ', '+')}"

        html = await self._request_text(url)
        if not html:
            return None

        result = self._parse_web_response(html, query)
        if result:
            result["discovered_via"] = "web_parse"
            return result

        return None

    def _parse_web_response(self, html: str, query: str) -> dict | None:
        """Parse embedded JSON data from Avito web page."""
        category_id = None
        params = {}

        # Look for categoryId in embedded JSON
        # Avito embeds config in window.__initialData__ or similar
        patterns = [
            r'"categoryId"\s*:\s*(\d+)',
            r'"mainCategory"\s*:\s*\{\s*"id"\s*:\s*(\d+)',
            r'categoryId=(\d+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                try:
                    category_id = int(match.group(1))
                    break
                except ValueError:
                    pass

        # Look for params in the page
        param_pattern = r'params\[(\d+)\]["\s]*[=:]\s*["\']?(\d+)'
        for match in re.finditer(param_pattern, html):
            param_id = match.group(1)
            param_value = match.group(2)
            params[f"params[{param_id}]"] = param_value

        if category_id or params:
            return {
                "category_id": category_id,
                "params": params,
            }

        return None

    async def discover_params(self, model_name: str) -> dict:
        """Discover Avito params for a product model.

        Tries search API then web parsing. Returns a result dict with:
        - category_id: int or None
        - params: dict of params[N]=value
        - discovered_via: str method name
        - error: str if all methods failed
        """
        logger.info("Discovering params for: %s", model_name)

        # Method A: Search API
        result = await self.discover_via_search(model_name)
        if result and (result.get("category_id") or result.get("params")):
            logger.info(
                "Discovered %s via search: cat=%s, params=%d",
                model_name,
                result.get("category_id"),
                len(result.get("params", {})),
            )
            return result

        await asyncio.sleep(random.uniform(8, 12))

        # Method B: Web page parsing
        result = await self.discover_via_web(model_name)
        if result and (result.get("category_id") or result.get("params")):
            logger.info(
                "Discovered %s via web: cat=%s, params=%d",
                model_name,
                result.get("category_id"),
                len(result.get("params", {})),
            )
            return result

        logger.warning("All discovery methods failed for: %s", model_name)
        return {
            "category_id": None,
            "params": {},
            "discovered_via": "none",
            "error": f"All discovery methods failed for '{model_name}'",
        }

    async def verify_params(
        self, category_id: int, params: dict[str, str]
    ) -> bool:
        """Verify discovered params by making a test search."""
        search_params = {
            "key": config.AVITO_API_KEY,
            "locationId": config.AVITO_LOCATION_ID,
            "categoryId": category_id,
            "limit": 3,
            "sort": "date",
        }
        search_params.update(params)

        data = await self._request(ITEMS_ENDPOINT, search_params)
        if not data:
            return False

        items = data.get("result", {}).get("items", [])
        real_items = [i for i in items if i.get("type") == "item"]
        return len(real_items) > 0

    async def discover_and_verify(self, model_name: str) -> dict:
        """Discover params and verify they return results."""
        result = await self.discover_params(model_name)

        if result.get("category_id") and not result.get("error"):
            await asyncio.sleep(random.uniform(4, 7))
            verified = await self.verify_params(
                result["category_id"], result.get("params", {})
            )
            result["verified"] = verified
            if not verified:
                logger.warning(
                    "Params for %s discovered but verification failed", model_name
                )
        else:
            result["verified"] = False

        return result

    async def discover_batch(
        self,
        models: list[str],
        delay: float = 8.0,
        progress_callback: Any = None,
    ) -> dict[str, dict]:
        """Discover params for a batch of models.

        Args:
            models: List of model names to discover.
            delay: Seconds between requests.
            progress_callback: Optional async callable(current, total, model, result).

        Returns:
            Dict mapping model name to discovery result.
        """
        results = {}
        total = len(models)

        for i, model in enumerate(models):
            result = await self.discover_and_verify(model)
            results[model] = result

            if progress_callback:
                await progress_callback(i + 1, total, model, result)

            if i < total - 1:
                await asyncio.sleep(delay)

        # Summary
        discovered = sum(
            1 for r in results.values()
            if r.get("category_id") and not r.get("error")
        )
        verified = sum(1 for r in results.values() if r.get("verified"))
        failed = total - discovered

        logger.info(
            "Batch discovery complete: %d/%d discovered, %d verified, %d failed",
            discovered, total, verified, failed,
        )

        return results
