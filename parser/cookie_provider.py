"""Playwright-based cookie provider for Avito.

Avito requires an 'ft' fingerprint cookie that is set by client-side JavaScript.
HTTP clients like curl_cffi or httpx cannot execute JS, so we use a headless
browser (Playwright + stealth) to obtain these cookies.

This follows the same approach as Duff89/parser_avito (484+ stars):
  1. Launch headless Chromium with anti-detection measures
  2. Visit a random non-existent ad page on Avito
  3. Wait for JS fingerprinting to set the 'ft' cookie
  4. Return all cookies for use in subsequent HTTP requests
"""
import asyncio
import logging
import random
import time
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# How long cookies stay valid before refresh (25 minutes)
COOKIE_TTL = 25 * 60

# Max wait for ft cookie (10 attempts × 5 seconds = 50 seconds)
FT_POLL_ATTEMPTS = 10
FT_POLL_INTERVAL = 5


class CookieProvider:
    """Acquires and caches Avito cookies via headless browser."""

    def __init__(self, proxy_url: str | None = None) -> None:
        self._proxy_url = proxy_url
        self._cookies: dict[str, str] = {}
        self._obtained_at: float = 0

    @property
    def cookies(self) -> dict[str, str]:
        return dict(self._cookies)

    @property
    def has_ft(self) -> bool:
        return "ft" in self._cookies

    @property
    def is_expired(self) -> bool:
        if not self._cookies:
            return True
        return (time.time() - self._obtained_at) > COOKIE_TTL

    async def ensure_cookies(self) -> dict[str, str]:
        """Get cookies, refreshing if expired or missing."""
        if not self.is_expired and self.has_ft:
            return self._cookies
        return await self.refresh()

    async def refresh(self) -> dict[str, str]:
        """Force-refresh cookies via Playwright."""
        logger.info("Refreshing Avito cookies via Playwright...")
        try:
            self._cookies = await self._get_cookies_playwright()
            self._obtained_at = time.time()
            if self.has_ft:
                logger.info(
                    "Got %d cookies (ft=%s...)",
                    len(self._cookies),
                    self._cookies["ft"][:20],
                )
            else:
                logger.warning(
                    "Got %d cookies but NO ft cookie!", len(self._cookies)
                )
        except Exception as e:
            logger.error("Failed to get cookies via Playwright: %s", e)
            self._cookies = {}
        return self._cookies

    def handle_block(self) -> None:
        """Invalidate cookies so they are refreshed on next use."""
        logger.info("Cookies invalidated due to block")
        self._cookies = {}
        self._obtained_at = 0

    async def _get_cookies_playwright(self) -> dict[str, str]:
        """Launch headless browser and extract cookies."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error(
                "playwright not installed! Run: "
                "pip install playwright playwright-stealth && "
                "playwright install chromium"
            )
            return {}

        # Try to use stealth plugin
        stealth = None
        try:
            from playwright_stealth import Stealth
            stealth = Stealth()
        except ImportError:
            logger.debug("playwright-stealth not installed, using basic stealth")

        proxy_config = None
        if self._proxy_url:
            parsed = urlparse(self._proxy_url)
            proxy_config = {
                "server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}",
            }
            if parsed.username:
                proxy_config["username"] = parsed.username
            if parsed.password:
                proxy_config["password"] = parsed.password

        cookies: dict[str, str] = {}

        if stealth:
            pw_ctx = stealth.use_async(async_playwright())
        else:
            pw_ctx = async_playwright()

        async with pw_ctx as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )

            context = await browser.new_context(
                proxy=proxy_config,
                locale="ru-RU",
                viewport={"width": 1920, "height": 1080},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/136.0.0.0 Safari/537.36"
                ),
            )

            page = await context.new_page()

            # Manual stealth if plugin not available
            if not stealth:
                await page.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                    Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});
                    Object.defineProperty(navigator, 'vendor', {get: () => 'Google Inc.'});
                    window.chrome = {runtime: {}};
                    Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3]});
                    Object.defineProperty(navigator, 'languages', {get: () => ['ru-RU', 'ru']});
                """)

            # Visit a random non-existent ad (like Duff89/parser_avito)
            random_id = str(random.randint(1111111111, 9999999999))
            target_url = f"https://www.avito.ru/{random_id}"

            try:
                await page.goto(
                    target_url, timeout=60000, wait_until="domcontentloaded"
                )
            except Exception as e:
                logger.debug("Page load (expected to be 404): %s", e)

            # Poll for ft cookie
            for attempt in range(FT_POLL_ATTEMPTS):
                raw_cookie = await page.evaluate("() => document.cookie")
                cookie_dict = _parse_cookie_string(raw_cookie)

                if cookie_dict.get("ft"):
                    logger.debug("ft cookie obtained on attempt %d", attempt + 1)
                    cookies = cookie_dict
                    break

                await asyncio.sleep(FT_POLL_INTERVAL)
            else:
                # Return whatever we got even without ft
                raw_cookie = await page.evaluate("() => document.cookie")
                cookies = _parse_cookie_string(raw_cookie)
                logger.warning("ft cookie not obtained after %d attempts", FT_POLL_ATTEMPTS)

            await browser.close()

        return cookies


def _parse_cookie_string(raw: str) -> dict[str, str]:
    """Parse 'key1=val1; key2=val2' into a dict."""
    result: dict[str, str] = {}
    for pair in raw.split(";"):
        pair = pair.strip()
        if "=" in pair:
            k, v = pair.split("=", 1)
            result[k.strip()] = v.strip()
    return result
