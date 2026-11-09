"""SpamDetector — rate and repetition analysis per source IP.

Two complementary signals:

* **Flood / DoS (R004):** one source IP exceeding a packets-per-second rate.
* **Spam (R005):** the same payload repeated many times in a short window, which
  is the fingerprint of an automated bot rather than organic traffic.

Both use sliding time windows so they measure *current* behaviour, not lifetime
totals, and both reset cleanly as traffic returns to normal.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass


@dataclass
class RateVerdict:
    src_ip: str
    rate: float
    flooding: bool


class SpamDetector:
    def __init__(
        self,
        packets_per_sec: int = 500,
        identical_payloads: int = 50,
        repeat_window: float = 5.0,
    ):
        self.packets_per_sec = packets_per_sec
        self.identical_payloads = identical_payloads
        self.repeat_window = repeat_window
        # Per-source arrival timestamps within the last second.
        self._arrivals: dict[str, deque[float]] = defaultdict(deque)
        # Per-(source, payload_hash) timestamps within the repeat window.
        self._payloads: dict[tuple[str, str], deque[float]] = defaultdict(deque)

    def observe_rate(self, src_ip: str, now: float | None = None) -> RateVerdict:
        now = time.time() if now is None else now
        q = self._arrivals[src_ip]
        q.append(now)
        cutoff = now - 1.0
        while q and q[0] < cutoff:
            q.popleft()
        rate = float(len(q))
        return RateVerdict(src_ip=src_ip, rate=rate, flooding=rate > self.packets_per_sec)

    def observe_payload(
        self, src_ip: str, payload_hash: str, now: float | None = None
    ) -> int | None:
        """Return the repeat-count if the identical-payload threshold is crossed."""
        now = time.time() if now is None else now
        key = (src_ip, payload_hash)
        q = self._payloads[key]
        q.append(now)
        cutoff = now - self.repeat_window
        while q and q[0] < cutoff:
            q.popleft()
        if len(q) >= self.identical_payloads:
            return len(q)
        return None
