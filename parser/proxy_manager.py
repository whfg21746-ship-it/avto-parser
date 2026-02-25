"""Proxy manager with health-check and auto-recovery."""

import logging
import random
import time

from parser.resilience import NoHealthyProxyError

logger = logging.getLogger(__name__)

# How long a failed proxy stays in quarantine before recovery attempt
RECOVERY_TIMEOUT = 300  # 5 minutes


class ProxyManager:
    def __init__(self, proxies: list[str]) -> None:
        self.healthy: set[str] = set(proxies)
        self.failed: dict[str, tuple[int, float]] = {}  # proxy -> (fail_count, last_fail_time)
        self._all_proxies: list[str] = list(proxies)

    def get_proxy(self) -> str | None:
        """Return a random healthy proxy, or None if no proxies configured."""
        if not self._all_proxies:
            return None
        if not self.healthy:
            self._recover_failed()
        if not self.healthy:
            raise NoHealthyProxyError(
                f"All {len(self._all_proxies)} proxies dead"
            )
        return random.choice(list(self.healthy))

    def mark_failed(self, proxy: str) -> None:
        """Mark a proxy as unhealthy."""
        if proxy not in self._all_proxies:
            return
        self.healthy.discard(proxy)
        count = self.failed.get(proxy, (0, 0))[0] + 1
        self.failed[proxy] = (count, time.time())
        logger.warning(
            "Proxy marked failed (%d times): %s [%d healthy remaining]",
            count, proxy, len(self.healthy),
        )

    def mark_healthy(self, proxy: str) -> None:
        """Return a proxy to healthy pool."""
        if proxy not in self._all_proxies:
            return
        self.healthy.add(proxy)
        self.failed.pop(proxy, None)

    def force_rotate(self) -> None:
        """Compatibility shim: old code calls this on errors."""
        pass

    def _recover_failed(self) -> None:
        """Recover proxies that have been in quarantine long enough."""
        now = time.time()
        recovered = []
        for proxy, (count, last_fail) in list(self.failed.items()):
            if now - last_fail > RECOVERY_TIMEOUT:
                self.healthy.add(proxy)
                del self.failed[proxy]
                recovered.append(proxy)
        if recovered:
            logger.info("Recovered %d proxies from quarantine", len(recovered))

    @property
    def has_proxies(self) -> bool:
        return len(self._all_proxies) > 0

    @property
    def count(self) -> int:
        return len(self._all_proxies)

    @property
    def healthy_count(self) -> int:
        return len(self.healthy)

    def status(self) -> str:
        """Human-readable status string."""
        return (
            f"{len(self.healthy)}/{len(self._all_proxies)} healthy, "
            f"{len(self.failed)} in quarantine"
        )
