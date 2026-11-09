"""SequenceTracker — detect gaps (loss/theft) and duplicates (replay) in the stream.

The sender assigns a monotonically increasing sequence number to every packet.
If the receiver observes 1,2,4,5 it knows packet 3 never arrived — it was lost or
stolen in transit (Rule R001). If it observes the same sequence number twice, that
is a duplicate worth correlating with the blockchain replay check (Rule R003).
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field


@dataclass
class GapEvent:
    missing: list[int]
    window_seconds: float
    detected_at: float = field(default_factory=time.time)


class SequenceTracker:
    def __init__(self, max_gap: int = 3, window_seconds: float = 10.0):
        self.max_gap = max_gap
        self.window_seconds = window_seconds
        self._highest: int = -1
        self._seen: set[int] = set()
        # (timestamp, seq) of recently missing numbers, for windowed counting.
        self._recent_missing: deque[tuple[float, int]] = deque()

    def observe(self, seq: int, now: float | None = None) -> tuple[list[int], bool]:
        """Record an observed sequence number.

        Returns ``(newly_missing, is_duplicate)``.
        """
        now = time.time() if now is None else now
        is_duplicate = seq in self._seen
        self._seen.add(seq)

        newly_missing: list[int] = []
        if self._highest >= 0 and seq > self._highest + 1:
            # Everything strictly between the previous high and this seq is missing.
            for missing in range(self._highest + 1, seq):
                if missing not in self._seen:
                    newly_missing.append(missing)
                    self._recent_missing.append((now, missing))
        if seq > self._highest:
            self._highest = seq

        return newly_missing, is_duplicate

    def gap_exceeded(self, now: float | None = None) -> GapEvent | None:
        """Return a :class:`GapEvent` if too many packets are missing in-window."""
        now = time.time() if now is None else now
        cutoff = now - self.window_seconds
        while self._recent_missing and self._recent_missing[0][0] < cutoff:
            self._recent_missing.popleft()
        # A number counts as still-missing only if we never later observed it.
        still_missing = [s for _, s in self._recent_missing if s not in self._seen]
        if len(still_missing) > self.max_gap:
            return GapEvent(missing=sorted(set(still_missing)),
                            window_seconds=self.window_seconds, detected_at=now)
        return None
