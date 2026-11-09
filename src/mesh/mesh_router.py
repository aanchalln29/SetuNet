"""SETU-NET Mesh Router and Multi-Hop Controlled Flooding Engine.

Implements the complete 8-step methodology specified in Slide 6:
  Step 1: User triggers an alert (SOS, Evacuation, Troop Movement, General).
  Step 2: Encode alert with type, GPS location, timestamp, and digital signature.
  Step 3: Discover nearby phones using Wi-Fi Direct or Wi-Fi Aware.
  Step 4: Send alert to all active peer connections.
  Step 5: Every receiving phone performs a duplicate check (discard if duplicate).
  Step 6: Place alert in priority queue (SOS processed before general alerts).
  Step 7: Forward new alert with TTL reduced by one (initial TTL = 6; drop when TTL = 0).
  Step 8: Display alert, activate notification/alarm, store in SQLite, send ACK.
"""

from __future__ import annotations

import copy
import math
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from .ack_manager import AckManager
from .battery import BatteryMonitor
from .clock_sync import ClockSyncEstimator
from .crypto import KeyPair, generate_keypair, sign_message, verify_signature
from .duplicate_cache import DuplicateCache
from .priority_queue import PriorityMeshQueue
from .protocol import AckMessage, AlertCategory, AlertMessage, GPSLocation
from .storage import MeshDatabase


# Default Wi-Fi Direct P2P range targets (Slide 5: 150 to 200 metres in open conditions)
DEFAULT_MAX_RANGE_METERS = 200.0


def haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in meters between two GPS coordinates."""
    r = 6371000.0  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r * c


@dataclass
class MeshNode:
    """Represents an Android phone node participating in the SETU-NET mesh."""
    node_id: str
    label: str
    role: str               # "sender", "relay", "rescue", "civilian", "troop", "control"
    latitude: float
    longitude: float
    altitude: float = 10.0
    keypair: KeyPair = field(default_factory=generate_keypair)
    is_online: bool = True
    indoor_mode: bool = False  # Reduces effective Wi-Fi range (Slide 9 limitation)
    store_and_carry_buffer: list[AlertMessage] = field(default_factory=list)

    def effective_range_meters(self) -> float:
        # Open conditions: 200m; Indoor / through walls: ~45m (Slide 9)
        return 45.0 if self.indoor_mode else DEFAULT_MAX_RANGE_METERS


class MeshRouter:
    """Orchestrates controlled flooding, peer discovery, TTL forwarding, and reverse ACKs."""

    def __init__(
        self,
        storage: MeshDatabase,
        ack_manager: AckManager,
        battery: BatteryMonitor,
    ):
        self.storage = storage
        self.ack_manager = ack_manager
        self.battery = battery
        
        self.nodes: dict[str, MeshNode] = {}
        self.priority_queues: dict[str, PriorityMeshQueue] = {}
        self.duplicate_caches: dict[str, DuplicateCache] = {}
        self.clock_estimators: dict[str, ClockSyncEstimator] = {}
        
        self._lock = threading.RLock()
        self.total_transmissions = 0
        self.total_receptions = 0
        self.ttl_dropped_count = 0
        self.tampered_dropped_count = 0

    def add_node(self, node: MeshNode) -> None:
        with self._lock:
            self.nodes[node.node_id] = node
            self.priority_queues[node.node_id] = PriorityMeshQueue()
            self.duplicate_caches[node.node_id] = DuplicateCache()
            self.clock_estimators[node.node_id] = ClockSyncEstimator(node.node_id)
            self.battery.register_node(node.node_id)
            self.storage.register_node(
                node_id=node.node_id,
                label=node.label,
                role=node.role,
                lat=node.latitude,
                lon=node.longitude,
                battery_pct=100.0,
                status="ONLINE" if node.is_online else "OFFLINE",
            )

    def get_node(self, node_id: str) -> Optional[MeshNode]:
        with self._lock:
            return self.nodes.get(node_id)

    def get_neighbors(self, node_id: str) -> list[str]:
        """Step 3: Discover nearby phones within active Wi-Fi Direct / Wi-Fi Aware range."""
        with self._lock:
            node = self.nodes.get(node_id)
            if not node or not node.is_online:
                return []

            neighbors = []
            max_range = node.effective_range_meters()
            for other_id, other_node in self.nodes.items():
                if other_id == node_id or not other_node.is_online:
                    continue
                dist = haversine_distance_meters(
                    node.latitude, node.longitude,
                    other_node.latitude, other_node.longitude,
                )
                if dist <= max_range:
                    neighbors.append(other_id)
            return neighbors

    def broadcast_alert(
        self,
        sender_id: str,
        category: AlertCategory,
        payload_text: str,
        location: GPSLocation | None = None,
        initial_ttl: int = 6,
        time_offset: float = 0.0,
        tamper_signature: bool = False,
        meta: dict[str, Any] | None = None,
    ) -> AlertMessage:
        """Step 1 & 2: User triggers alert; application encodes with GPS, timestamp & Ed25519 signature."""
        with self._lock:
            sender = self.nodes.get(sender_id)
            if not sender:
                raise ValueError(f"Unknown sender node: {sender_id}")

            loc = location or GPSLocation(
                latitude=sender.latitude,
                longitude=sender.longitude,
                altitude_meters=sender.altitude,
            )

            msg_id = f"SETU-{category.name[:3]}-{int(time.time() * 1000) % 1000000:06d}"
            alert = AlertMessage(
                message_id=msg_id,
                category=category,
                origin_node_id=sender_id,
                payload_text=payload_text,
                location=loc,
                timestamp=time.time(),
                ttl=initial_ttl,
                hop_count=0,
                hop_path=[sender_id],
                time_offset_est=time_offset,
                public_key=sender.keypair.public_hex,
                meta=meta or {},
            )

            # Cryptographic signature
            canonical_bytes = alert.canonical_bytes()
            if tamper_signature:
                alert.signature = "deadbeef" * 16  # Tampered invalid signature
            else:
                alert.signature = sign_message(sender.keypair, canonical_bytes)

            # Origin marks as seen in duplicate cache to prevent self-re-forwarding
            self.duplicate_caches[sender_id].check_and_mark(alert.message_id)
            self.storage.save_alert(alert, status="BROADCASTED")

            # Track sender battery drain
            self.battery.record_activity(sender_id, tx_count=1, scan_seconds=0.2)
            self.total_transmissions += 1

            # Dispatch propagation
            self._propagate_flooding(alert, current_node_id=sender_id)
            
            # Slide 7: Out-of-range control device is a baseline test, not an in-range reachable target
            total_active_peers = sum(
                1 for n in self.nodes.values()
                if n.is_online and n.node_id != sender_id and n.role != "control"
            )
            self.ack_manager.generate_delivery_report(alert, total_active_peers)
            return alert

    def _propagate_flooding(self, alert: AlertMessage, current_node_id: str) -> None:
        """Controlled flooding recursive step across reachable neighbors."""
        neighbors = self.get_neighbors(current_node_id)
        if not neighbors:
            # Slide 9: device may store alert until physically in range of peers
            node = self.nodes.get(current_node_id)
            if node:
                node.store_and_carry_buffer.append(copy.deepcopy(alert))
            return

        # Breadth-first wave dispatch to all active peer connections (Step 4)
        for neighbor_id in neighbors:
            # Skip if this neighbor was the immediate previous hop to prevent instant ping-pong
            if len(alert.hop_path) >= 2 and neighbor_id == alert.hop_path[-2]:
                continue
            self._receive_at_node(neighbor_id, alert, from_node_id=current_node_id)

    def _receive_at_node(self, node_id: str, alert: AlertMessage, from_node_id: str) -> None:
        """Executes Steps 5, 6, 7 & 8 at a receiving phone."""
        with self._lock:
            node = self.nodes.get(node_id)
            if not node or not node.is_online:
                return

            self.total_receptions += 1
            self.battery.record_activity(node_id, rx_count=1)

            # Security Verification: Verify Ed25519 signature
            canonical_bytes = alert.canonical_bytes()
            is_valid_sig = verify_signature(alert.public_key, canonical_bytes, alert.signature)
            if not is_valid_sig:
                self.tampered_dropped_count += 1
                self.storage.log_event(
                    event_type="SIGNATURE_VERIFICATION_FAILED",
                    message_id=alert.message_id,
                    node_id=node_id,
                    details={"reason": "Invalid or tampered Ed25519 signature", "from": from_node_id},
                )
                return  # REJECT AND DROP!

            # Step 5: Duplicate check (discard if already received)
            dup_cache = self.duplicate_caches[node_id]
            if dup_cache.check_and_mark(alert.message_id):
                # Duplicate! Discard copy to prevent loops & broadcast storms
                self.storage.log_event(
                    event_type="DUPLICATE_SUPPRESSED",
                    message_id=alert.message_id,
                    node_id=node_id,
                    details={"from": from_node_id},
                )
                return

            # Step 6: Place in priority queue (SOS preempts general alerts)
            p_queue = self.priority_queues[node_id]
            p_queue.put(alert)

            # Step 8: Pop and display alert, activate alarm, save to SQLite, and send ACK
            processed_alert = p_queue.get()
            if not processed_alert:
                return

            self.storage.save_alert(processed_alert, status="DELIVERED")

            # Generate reverse ACK
            ack = self.ack_manager.create_ack(
                alert=processed_alert,
                receiving_node_id=node_id,
                received_timestamp=time.time(),
            )
            self.ack_manager.record_ack(ack)
            self.storage.save_ack(ack)

            # Step 7: Check TTL; forward with TTL reduced by 1
            if processed_alert.ttl <= 1:
                # TTL has reached 0 after decrement; do not forward further (Slide 6)
                self.ttl_dropped_count += 1
                self.storage.log_event(
                    event_type="TTL_EXPIRED",
                    message_id=processed_alert.message_id,
                    node_id=node_id,
                    details={"final_hop_count": processed_alert.hop_count + 1},
                )
                return

            # Decrement TTL and increment hop count
            forward_alert = copy.deepcopy(processed_alert)
            forward_alert.ttl -= 1
            forward_alert.hop_count += 1
            forward_alert.hop_path.append(node_id)

            # Forward to next ring of peers
            self.battery.record_activity(node_id, tx_count=1)
            self.total_transmissions += 1
            self._propagate_flooding(forward_alert, current_node_id=node_id)
