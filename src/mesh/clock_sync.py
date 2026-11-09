"""Peer-to-Peer Time Difference Estimation and Clock Synchronization.

Estimates relative clock offsets between nearby phones over ad-hoc Wi-Fi connections
without requiring cellular backhaul or GPS time lock, as specified in Slide 5:
'to estimate time differences between phones so that timestamps can be compared more accurately.'
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class PeerTimeOffset:
    peer_id: str
    estimated_offset_seconds: float
    round_trip_delay_ms: float
    last_updated: float
    samples_count: int


class ClockSyncEstimator:
    """Pairwise time difference estimator between mesh peer devices.
    
    Uses symmetric two-way timestamp exchange (Cristian's algorithm variant):
      - t0: sender local transmit timestamp
      - t1: receiver local receive timestamp
      - t2: receiver local reply timestamp
      - t3: sender local response receive timestamp
      
      offset = ((t1 - t0) + (t2 - t3)) / 2
      round_trip_delay = (t3 - t0) - (t2 - t1)
    """

    def __init__(self, local_node_id: str):
        self.local_node_id = local_node_id
        self._offsets: dict[str, PeerTimeOffset] = {}
        self._lock = threading.RLock()

    def record_exchange(
        self,
        peer_id: str,
        t0: float,
        t1: float,
        t2: float,
        t3: float,
    ) -> PeerTimeOffset:
        """Compute and store clock offset relative to peer_id."""
        offset = ((t1 - t0) + (t2 - t3)) / 2.0
        rtt_seconds = max(0.0001, (t3 - t0) - (t2 - t1))
        rtt_ms = rtt_seconds * 1000.0

        with self._lock:
            existing = self._offsets.get(peer_id)
            if existing:
                # Exponential moving average filter
                alpha = 0.3
                smoothed_offset = (1.0 - alpha) * existing.estimated_offset_seconds + alpha * offset
                smoothed_rtt = (1.0 - alpha) * existing.round_trip_delay_ms + alpha * rtt_ms
                record = PeerTimeOffset(
                    peer_id=peer_id,
                    estimated_offset_seconds=smoothed_offset,
                    round_trip_delay_ms=smoothed_rtt,
                    last_updated=time.time(),
                    samples_count=existing.samples_count + 1,
                )
            else:
                record = PeerTimeOffset(
                    peer_id=peer_id,
                    estimated_offset_seconds=offset,
                    round_trip_delay_ms=rtt_ms,
                    last_updated=time.time(),
                    samples_count=1,
                )
            self._offsets[peer_id] = record
            return record

    def get_offset(self, peer_id: str) -> float:
        """Get estimated offset in seconds for a specific peer (0.0 if unknown)."""
        with self._lock:
            record = self._offsets.get(peer_id)
            return record.estimated_offset_seconds if record else 0.0

    def normalize_timestamp(self, timestamp: float, peer_id: str) -> float:
        """Adjust a peer's local timestamp to our local reference frame."""
        offset = self.get_offset(peer_id)
        return timestamp - offset

    def summary(self) -> dict[str, dict[str, float | int]]:
        with self._lock:
            return {
                peer_id: {
                    "offset_sec": round(rec.estimated_offset_seconds, 4),
                    "offset_ms": round(rec.estimated_offset_seconds * 1000.0, 1),
                    "rtt_ms": round(rec.round_trip_delay_ms, 2),
                    "samples": rec.samples_count,
                    "last_updated": round(rec.last_updated, 1),
                }
                for peer_id, rec in self._offsets.items()
            }
