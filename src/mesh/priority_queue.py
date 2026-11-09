"""Priority Mesh Queue with Preemption.

Ensures that urgent SOS alerts are forwarded and processed before lower-priority
messages (Evacuation, Troop Movement, and General) as specified in Slides 4, 6, 7, 8 & 10.
"""

from __future__ import annotations

import heapq
import threading
import time
from dataclasses import dataclass, field
from typing import Any, List, Optional

from .protocol import AlertCategory, AlertMessage


@dataclass(order=True)
class PrioritizedItem:
    """Internal item wrapper for heap ordering.
    
    Order:
      1. priority (0 = SOS, 1 = Evac, 2 = Troop, 3 = General)
      2. timestamp (FIFO among alerts of equal priority)
      3. counter (tie-breaker for deterministic sorting)
    """
    priority: int
    timestamp: float
    counter: int
    alert: AlertMessage = field(compare=False)


class PriorityMeshQueue:
    """Thread-safe priority queue for phone mesh transmission and processing.
    
    Preemption:
    When an SOS alert arrives and lower-priority alerts (Evac, Troop, General)
    are waiting in queue, the SOS alert jumps ahead to the front of the queue.
    """

    def __init__(self, maxsize: int = 500):
        self.maxsize = maxsize
        self._heap: list[PrioritizedItem] = []
        self._counter = 0
        self._lock = threading.RLock()
        self._not_empty = threading.Condition(self._lock)
        
        # Metrics
        self.total_enqueued = 0
        self.total_dequeued = 0
        self.preemptions_count = 0  # Number of times an SOS alert passed a lower-priority message

    def put(self, alert: AlertMessage, block: bool = True, timeout: float | None = None) -> bool:
        """Enqueue an alert based on its priority."""
        with self._lock:
            # Check for preemption: if queue has lower priority alerts, SOS preempts
            if alert.category == AlertCategory.SOS and self._heap:
                lowest_in_queue = max(item.priority for item in self._heap)
                if lowest_in_queue > AlertCategory.SOS:
                    self.preemptions_count += 1

            self._counter += 1
            item = PrioritizedItem(
                priority=alert.priority,
                timestamp=alert.timestamp,
                counter=self._counter,
                alert=alert,
            )
            heapq.heappush(self._heap, item)
            self.total_enqueued += 1
            self._not_empty.notify()
            return True

    def get(self, block: bool = False, timeout: float | None = None) -> Optional[AlertMessage]:
        """Pop the highest priority alert from the queue."""
        with self._lock:
            if not self._heap:
                if not block:
                    return None
                if not self._not_empty.wait(timeout=timeout):
                    return None
            if not self._heap:
                return None
            item = heapq.heappop(self._heap)
            self.total_dequeued += 1
            return item.alert

    def peek(self) -> Optional[AlertMessage]:
        """Inspect the next alert to be dispatched without removing it."""
        with self._lock:
            if not self._heap:
                return None
            return self._heap[0].alert

    def qsize(self) -> int:
        with self._lock:
            return len(self._heap)

    def is_empty(self) -> bool:
        with self._lock:
            return len(self._heap) == 0

    def snapshot(self) -> list[dict[str, Any]]:
        """Return human-readable ordered queue contents for UI visualization."""
        with self._lock:
            # Sort a copy according to heap order
            ordered = sorted(self._heap)
            return [
                {
                    "message_id": item.alert.message_id,
                    "category": item.alert.category.name,
                    "category_label": item.alert.category.label,
                    "priority": item.priority,
                    "origin_node_id": item.alert.origin_node_id,
                    "payload_preview": item.alert.payload_text[:40],
                    "timestamp": item.alert.timestamp,
                    "ttl": item.alert.ttl,
                    "hop_count": item.alert.hop_count,
                    "badge_color": item.alert.category.badge_color,
                }
                for item in ordered
            ]

    def stats(self) -> dict[str, Any]:
        with self._lock:
            category_counts = {cat.name: 0 for cat in AlertCategory}
            for item in self._heap:
                category_counts[item.alert.category.name] += 1

            return {
                "current_size": len(self._heap),
                "total_enqueued": self.total_enqueued,
                "total_dequeued": self.total_dequeued,
                "preemptions_count": self.preemptions_count,
                "category_counts": category_counts,
            }
