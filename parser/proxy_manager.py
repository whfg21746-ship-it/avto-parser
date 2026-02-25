"""Proxy manager with health-check and auto-recovery."""

import logging
import random
import time

from parser.resilience import NoHealthyProxyError

logger = logging.getLogger(__name__)

# How many consecutive failures before quarantining a proxy
FAIL_THRESHOLD = 3

# How long a failed proxy stays in quarantine before recovery attempt
RECOVERY_TIMEOUT = 120  # 2 minutes


class ProxyManager:
    def __init__(self, proxies: list[str]) -> None:
        self.healthy: set[str] = set(proxies)
        self.quarantined: dict[str, tuple[int, float]] = {}  # proxy -> (fail_count, quarantine_time)
        self._all_proxies: list[str] = list(proxies)
        # Track consecutive failures for proxies still in healthy pool
        self._consecutive_fails: dict[str, int] = {}

    def get_proxy(self) -> str | None:
        """Return a random healthy proxy, or None if no proxies configured."""
        if not self._all_proxies:
            return None
        if not self.healthy:
            self._recover_quarantined()
        if not self.healthy:
            raise NoHealthyProxyError(
                f"All {len(self._all_proxies)} proxies dead"
            )
        return random.choice(list(self.healthy))

    def mark_failed(self, proxy: str) -> None:
        """Register a failure for a proxy.

        The proxy stays in the healthy pool until it accumulates
        FAIL_THRESHOLD consecutive failures. This prevents a single
        dropped connection from killing the entire proxy pool.
        """
        if proxy not in self._all_proxies:
            return

        self._consecutive_fails[proxy] = self._consecutive_fails.get(proxy, 0) + 1
        fails = self._consecutive_fails[proxy]

        if fails < FAIL_THRESHOLD:
            logger.info(
                "Proxy failure %d/%d (still healthy): %s",
                fails, FAIL_THRESHOLD, proxy[:50],
            )
            return

        # Threshold reached — quarantine
        self.healthy.discard(proxy)
        total = self.quarantined.get(proxy, (0, 0))[0] + 1
        self.quarantined[proxy] = (total, time.time())
        self._consecutive_fails.pop(proxy, None)
        logger.warning(
            "Proxy quarantined (%d times total): %s [%d healthy remaining]",
            total, proxy[:50], len(self.healthy),
        )

    def mark_healthy(self, proxy: str) -> None:
        """Return a proxy to healthy pool and reset failure counter."""
        if proxy not in self._all_proxies:
            return
        self.healthy.add(proxy)
        self.quarantined.pop(proxy, None)
        self._consecutive_fails.pop(proxy, None)

    def force_rotate(self) -> None:
        """Compatibility shim: old code calls this on errors."""
        pass

    def _recover_quarantined(self) -> None:
        """Recover proxies that have been in quarantine long enough."""
        now = time.time()
        recovered = []
        for proxy, (count, quarantine_time) in list(self.quarantined.items()):
            if now - quarantine_time > RECOVERY_TIMEOUT:
                self.healthy.add(proxy)
                del self.quarantined[proxy]
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
            f"{len(self.quarantined)} in quarantine"
        )
