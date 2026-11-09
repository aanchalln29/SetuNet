"""Duplicate Detection and Flood Suppression Cache.

Prevents broadcast storms, routing loops, and unnecessary retransmissions
across phone-to-phone Wi-Fi mesh as specified in Slides 5, 6, 7 & 10.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from typing import Optional, Tuple


class DuplicateCache:
    """Thread-safe LRU duplicate suppression cache with TTL eviction.
    
    Slide 6, Step 5:
    'every receiving phone performs a duplicate check. If the alert has
     already been received, the duplicate copy is discarded.'
    """

    def __init__(self, max_entries: int = 1000, window_seconds: float = 300.0):
        self.max_entries = max_entries
        self.window_seconds = window_seconds
        self._cache: OrderedDict[str, float] = OrderedDict()  # message_id -> timestamp seen
        self._lock = threading.RLock()
        self.total_seen = 0
        self.duplicates_suppressed = 0

    def check_and_mark(self, message_id: str, now: float | None = None) -> bool:
        """Check if message_id was seen before.
        
        Returns:
            True if message is a DUPLICATE (should be discarded).
            False if message is FRESH (new alert, should be processed).
        """
        now = now if now is not None else time.time()
        with self._lock:
            self.total_seen += 1
            self._purge_expired(now)

            if message_id in self._cache:
                self.duplicates_suppressed += 1
                # Refresh position in LRU
                self._cache.move_to_end(message_id)
                return True  # Duplicate! Discard!

            # Fresh packet
            self._cache[message_id] = now
            if len(self._cache) > self.max_entries:
                self._cache.popitem(last=False)
            return False  # Not duplicate

    def is_duplicate(self, message_id: str) -> bool:
        """Read-only check without inserting."""
        with self._lock:
            return message_id in self._cache

    def _purge_expired(self, now: float) -> None:
        """Remove entries older than window_seconds."""
        cutoff = now - self.window_seconds
        while self._cache:
            first_key, first_time = next(iter(self._cache.items()))
            if first_time < cutoff:
                del self._cache[first_key]
            else:
                break

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self.total_seen = 0
            self.duplicates_suppressed = 0

    def stats(self) -> dict[str, int | float]:
        with self._lock:
            return {
                "cached_entries": len(self._cache),
                "total_seen": self.total_seen,
                "duplicates_suppressed": self.duplicates_suppressed,
                "suppression_ratio": round(
                    self.duplicates_suppressed / max(1, self.total_seen), 3
                ),
            }
