import logging
import random

logger = logging.getLogger(__name__)


class ProxyManager:
    def __init__(self, proxies: list[str]) -> None:
        self.proxies: list[str] = list(proxies)
        self.current_index: int = 0
        self.request_count: int = 0
        self._rotate_threshold: int = random.randint(10, 20)

    def get_proxy(self) -> str | None:
        if not self.proxies:
            return None
        proxy = self.proxies[self.current_index]
        self.request_count += 1
        if self.request_count >= self._rotate_threshold:
            self._rotate()
        return proxy

    def _rotate(self) -> None:
        if not self.proxies:
            return
        self.current_index = (self.current_index + 1) % len(self.proxies)
        self.request_count = 0
        self._rotate_threshold = random.randint(10, 20)
        logger.debug("Rotated to proxy index %d", self.current_index)

    def force_rotate(self) -> None:
        self._rotate()
        logger.info("Force-rotated proxy after error")

    def remove_proxy(self, proxy: str) -> None:
        if proxy in self.proxies:
            self.proxies.remove(proxy)
            if self.current_index >= len(self.proxies):
                self.current_index = 0
            logger.warning("Removed proxy %s, %d remaining", proxy, len(self.proxies))

    @property
    def has_proxies(self) -> bool:
        return len(self.proxies) > 0

    @property
    def count(self) -> int:
        return len(self.proxies)
