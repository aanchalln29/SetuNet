"""Battery Consumption Model for Phone-to-Phone Mesh Communication.

Models energy drain (in milliampere-hours / mAh) across Wi-Fi Direct / Wi-Fi Aware
peer discovery, transmission, reception, and idle states as specified in Slides 7 & 8:
'The main metrics we will measure are: Delivery ratio, Per-hop latency,
 End-to-end latency, Duplicate count, Battery consumption, Number of acknowledged nodes.'
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Dict


# Baseline empirical power consumption ratings for Android Wi-Fi Direct (3.8V typical battery)
# Current draw in mA:
CURRENT_SCAN_MA = 180.0       # Active P2P channel scanning & peer discovery
CURRENT_TX_MA = 240.0         # RF packet broadcast transmission
CURRENT_RX_MA = 140.0         # RF packet reception and crypto verification
CURRENT_IDLE_MESH_MA = 35.0   # Wi-Fi Direct periodic beaconing / listen state


@dataclass
class BatteryState:
    battery_capacity_mah: float = 4000.0   # Typical smartphone 4000 mAh battery
    remaining_mah: float = 4000.0
    scan_seconds: float = 0.0
    tx_packets: int = 0
    rx_packets: int = 0
    idle_seconds: float = 0.0
    start_time: float = 0.0

    @property
    def percentage(self) -> float:
        return max(0.0, min(100.0, round((self.remaining_mah / self.battery_capacity_mah) * 100.0, 1)))

    @property
    def consumed_mah(self) -> float:
        return round(self.battery_capacity_mah - self.remaining_mah, 2)


class BatteryMonitor:
    """Tracks and models battery drain for all participating mesh nodes."""

    def __init__(self, default_capacity_mah: float = 4000.0):
        self.default_capacity_mah = default_capacity_mah
        self._nodes: dict[str, BatteryState] = {}
        self._lock = threading.RLock()

    def register_node(self, node_id: str, capacity_mah: float | None = None) -> None:
        cap = capacity_mah or self.default_capacity_mah
        with self._lock:
            self._nodes[node_id] = BatteryState(
                battery_capacity_mah=cap,
                remaining_mah=cap,
                start_time=time.time(),
            )

    def record_activity(
        self,
        node_id: str,
        tx_count: int = 0,
        rx_count: int = 0,
        scan_seconds: float = 0.0,
    ) -> BatteryState:
        with self._lock:
            if node_id not in self._nodes:
                self.register_node(node_id)
            node = self._nodes[node_id]

            # Approximate packet transmission time (~15ms per packet burst)
            tx_time_hours = (tx_count * 0.015) / 3600.0
            rx_time_hours = (rx_count * 0.012) / 3600.0
            scan_time_hours = scan_seconds / 3600.0

            # Drain in mAh = current (mA) * time (hours)
            drain_mah = (
                (CURRENT_TX_MA * tx_time_hours) +
                (CURRENT_RX_MA * rx_time_hours) +
                (CURRENT_SCAN_MA * scan_time_hours)
            )

            node.remaining_mah = max(0.0, node.remaining_mah - drain_mah)
            node.tx_packets += tx_count
            node.rx_packets += rx_count
            node.scan_seconds += scan_seconds
            return node

    def get_node_battery(self, node_id: str) -> dict[str, float]:
        with self._lock:
            if node_id not in self._nodes:
                self.register_node(node_id)
            node = self._nodes[node_id]
            return {
                "capacity_mah": node.battery_capacity_mah,
                "remaining_mah": round(node.remaining_mah, 2),
                "consumed_mah": node.consumed_mah,
                "percentage": node.percentage,
                "tx_packets": node.tx_packets,
                "rx_packets": node.rx_packets,
            }

    def network_total_drain_mah(self) -> float:
        with self._lock:
            return round(sum(n.consumed_mah for n in self._nodes.values()), 2)
