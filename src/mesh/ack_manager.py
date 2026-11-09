"""Acknowledgement (ACK) Reporting and Reverse Hop Trace Manager.

Fulfills Slides 3, 6, 8, 9 & 10:
'reports observed delivery to the sender'
'Finally, the phone displays the alert, activates the appropriate notification
 or alarm, stores it in the local database and sends an acknowledgement.'
'The main metrics we will measure are: Delivery ratio, Per-hop latency,
 End-to-end latency, Duplicate count, Battery consumption, Number of acknowledged nodes.'
"""

from __future__ import annotations

import threading
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .protocol import AckMessage, AlertCategory, AlertMessage


@dataclass
class DeliveryReport:
    """Consolidated delivery metrics for a broadcast alert."""
    message_id: str
    category: AlertCategory
    origin_node_id: str
    total_target_nodes: int
    acknowledged_nodes_count: int
    delivery_ratio_pct: float
    avg_per_hop_latency_ms: float
    avg_end_to_end_latency_ms: float
    max_hop_depth: int
    acks: list[AckMessage] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "category": self.category.name,
            "category_label": self.category.label,
            "origin_node_id": self.origin_node_id,
            "total_target_nodes": self.total_target_nodes,
            "acknowledged_nodes_count": self.acknowledged_nodes_count,
            "delivery_ratio_pct": round(self.delivery_ratio_pct, 1),
            "target_delivery_met": self.delivery_ratio_pct >= 90.0,  # Slide 5: >= 90%
            "avg_per_hop_latency_ms": round(self.avg_per_hop_latency_ms, 1),
            "target_hop_delay_met": (self.avg_per_hop_latency_ms / 1000.0) < 5.0,  # Slide 5: < 5s
            "avg_end_to_end_latency_ms": round(self.avg_end_to_end_latency_ms, 1),
            "max_hop_depth": self.max_hop_depth,
            "acks_count": len(self.acks),
        }


class AckManager:
    """Collects and tracks reverse delivery acknowledgements for the sender phone."""

    def __init__(self):
        self._acks_by_msg: dict[str, list[AckMessage]] = defaultdict(list)
        self._reports: dict[str, DeliveryReport] = {}
        self._lock = threading.RLock()
        self.total_acks_received = 0

    def create_ack(
        self,
        alert: AlertMessage,
        receiving_node_id: str,
        received_timestamp: float | None = None,
        simulated_per_hop_latency_ms: float = 650.0,
    ) -> AckMessage:
        """Create an ACK packet at a receiving phone."""
        now = received_timestamp or time.time()
        hops = max(1, alert.hop_count)
        
        # End-to-end latency: either observed real difference or simulated per-hop model
        elapsed_real = (now - alert.timestamp) * 1000.0
        if elapsed_real < 10.0 or elapsed_real > 100000.0:
            # Synthetic / simulation fallback
            latency_ms = hops * simulated_per_hop_latency_ms
        else:
            latency_ms = elapsed_real

        # Reverse return path is the reverse of the forward hop path
        return_path = list(reversed(alert.hop_path))
        if receiving_node_id not in return_path:
            return_path.insert(0, receiving_node_id)

        ack = AckMessage(
            ack_id=f"ACK-{uuid.uuid4().hex[:8]}",
            original_message_id=alert.message_id,
            alert_category=alert.category,
            ack_node_id=receiving_node_id,
            origin_node_id=alert.origin_node_id,
            hops_to_node=hops,
            received_timestamp=now,
            latency_ms=latency_ms,
            return_path=return_path,
            status="DELIVERED",
        )
        return ack

    def record_ack(self, ack: AckMessage) -> None:
        """Store an incoming ACK packet arriving at the sender phone."""
        with self._lock:
            # Avoid duplicate ACKs from same node
            existing_nodes = {a.ack_node_id for a in self._acks_by_msg[ack.original_message_id]}
            if ack.ack_node_id not in existing_nodes:
                self._acks_by_msg[ack.original_message_id].append(ack)
                self.total_acks_received += 1

    def generate_delivery_report(
        self,
        alert: AlertMessage,
        total_reachable_nodes: int,
    ) -> DeliveryReport:
        """Compute the final delivery report and metrics against targets (Slide 5 & 8)."""
        with self._lock:
            acks = list(self._acks_by_msg.get(alert.message_id, []))
            ack_count = len(acks)
            ratio = (ack_count / max(1, total_reachable_nodes)) * 100.0

            if acks:
                avg_e2e = sum(a.latency_ms for a in acks) / ack_count
                avg_per_hop = sum(a.latency_ms / max(1, a.hops_to_node) for a in acks) / ack_count
                max_hops = max(a.hops_to_node for a in acks)
            else:
                avg_e2e = 0.0
                avg_per_hop = 0.0
                max_hops = 0

            report = DeliveryReport(
                message_id=alert.message_id,
                category=alert.category,
                origin_node_id=alert.origin_node_id,
                total_target_nodes=total_reachable_nodes,
                acknowledged_nodes_count=ack_count,
                delivery_ratio_pct=ratio,
                avg_per_hop_latency_ms=avg_per_hop,
                avg_end_to_end_latency_ms=avg_e2e,
                max_hop_depth=max_hops,
                acks=acks,
            )
            self._reports[alert.message_id] = report
            return report

    def get_acks(self, message_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return [a.to_dict() for a in self._acks_by_msg.get(message_id, [])]

    def get_report(self, message_id: str) -> Optional[dict[str, Any]]:
        with self._lock:
            rep = self._reports.get(message_id)
            return rep.to_dict() if rep else None

    def recent_acks(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            all_acks: list[AckMessage] = []
            for a_list in self._acks_by_msg.values():
                all_acks.extend(a_list)
            # Sort by received_timestamp descending
            all_acks.sort(key=lambda a: a.received_timestamp, reverse=True)
            return [a.to_dict() for a in all_acks[:limit]]
